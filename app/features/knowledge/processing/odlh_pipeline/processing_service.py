from __future__ import annotations

import logging
import time
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import ClassVar
from typing import Protocol
from uuid import UUID

from sqlmodel import Session
from sqlmodel import select

from app.core.config.environment import settings
from app.features.knowledge.common.chunk_persistence_service import ChunkEmbeddingGateway
from app.features.knowledge.common.chunk_persistence_service import KnowledgeChunkPersistenceService
from app.features.knowledge.common.metadata_service import KnowledgeMetadataService
from app.features.knowledge.common.text_source_service import KnowledgeTextSourceService
from app.features.knowledge.processing.odlh_pipeline.config.contants import DEFAULT_CHUNK_OVERLAP
from app.features.knowledge.processing.odlh_pipeline.config.contants import DEFAULT_CHUNK_SIZE
from app.features.knowledge.processing.odlh_pipeline.config.contants import DEFAULT_ENCODING_NAME
from app.features.knowledge.processing.odlh_pipeline.config.contants import DEFAULT_HYBRID_BACKEND_URL
from app.features.knowledge.processing.odlh_pipeline.config.contants import DEFAULT_OPENAI_EMBEDDING_MODEL
from app.features.knowledge.processing.odlh_pipeline.core.paths import read_doc
from app.features.knowledge.processing.odlh_pipeline.core.paths import resolve_pipeline_paths
from app.features.knowledge.processing.odlh_pipeline.models.models import ChunkingStrategy
from app.features.knowledge.processing.odlh_pipeline.models.models import PipelinePaths
from app.features.knowledge.processing.odlh_pipeline.services.analysis_service import AnalysisService
from app.features.knowledge.processing.odlh_pipeline.services.chunk_file_loader_service import ChunkFileLoaderService
from app.features.knowledge.processing.odlh_pipeline.services.chunk_service import ChunkService
from app.features.knowledge.processing.odlh_pipeline.services.cleanup_service import CleanupService
from app.features.knowledge.processing.odlh_pipeline.services.env_service import EnvService
from app.features.knowledge.processing.odlh_pipeline.services.parse_service import ParseService
from app.features.knowledge.processing.odlh_pipeline.services.text_chunk_export_service import TextChunkExportService
from app.infrastructure.models.knowledge_model import KnowledgeSourcesModel
from app.infrastructure.models.knowledge_model import ProcessingStatus

logger = logging.getLogger(__name__)


# ==================================================================================================
# PDF 변환 서비스 프로토콜
# --------------------------------------------------------------------------------------------------
# odlh 처리에서 필요한 convert 계약만 노출해 테스트 더블도 같은 타입으로 취급합니다
# ==================================================================================================
class ParseServiceProtocol(Protocol):
  # ================================================================================================
  # PDF 변환
  # ------------------------------------------------------------------------------------------------
  # 입력 PDF를 중간 산출물 경로 집합으로 변환합니다
  # ================================================================================================
  def convert(self, pdf_path: str | Path) -> PipelinePaths: ...


# ==================================================================================================
# PDF 변환 서비스 팩토리 인터페이스
# --------------------------------------------------------------------------------------------------
# source별 출력 디렉토리에 맞는 ParseService를 생성하기 위한 팩토리 계약입니다
# ==================================================================================================
class ParseServiceFactory(Protocol):
  # ================================================================================================
  # 변환 서비스 생성
  # ------------------------------------------------------------------------------------------------
  # 지정된 출력 루트와 백엔드 주소를 사용하는 변환 서비스를 반환합니다
  # ================================================================================================
  def __call__(self, output_dir: Path, backend_url: str) -> ParseServiceProtocol: ...


# ==================================================================================================
# odlh 파이프라인 처리 서비스
# --------------------------------------------------------------------------------------------------
# odlh 기반 PDF/Markdown/TXT 처리 후 공통 임베딩/DB 저장 계층으로 연결하는 워커용 서비스입니다
# ==================================================================================================
class KnowledgeProcessingService:
  _DIRECT_TEXT_EXTENSIONS: ClassVar[frozenset[str]] = frozenset({".md", ".txt"})

  # ================================================================================================
  # 초기화
  # ------------------------------------------------------------------------------------------------
  # odlh 파이프라인 단계 서비스와 공통 영속화 서비스를 주입받아 처리 준비를 합니다
  # ================================================================================================
  def __init__(
    self,
    embedding_service: ChunkEmbeddingGateway,
    analysis_service: AnalysisService | None = None,
    chunk_service: ChunkService | None = None,
    cleanup_service: CleanupService | None = None,
    text_chunk_export_service: TextChunkExportService | None = None,
    chunk_file_loader_service: ChunkFileLoaderService | None = None,
    chunk_persistence_service: KnowledgeChunkPersistenceService | None = None,
    parse_service_factory: ParseServiceFactory | None = None,
    backend_url: str = DEFAULT_HYBRID_BACKEND_URL,
  ):
    self._analysis_service = analysis_service or AnalysisService(
      chunk_size=DEFAULT_CHUNK_SIZE,
      encoding_name=DEFAULT_ENCODING_NAME,
      requested_strategy=ChunkingStrategy.AUTO,
    )
    self._chunk_service = chunk_service or ChunkService(
      chunk_size=DEFAULT_CHUNK_SIZE,
      chunk_overlap=DEFAULT_CHUNK_OVERLAP,
      encoding_name=DEFAULT_ENCODING_NAME,
      semantic_embedding_model=DEFAULT_OPENAI_EMBEDDING_MODEL,
      api_key=settings.OPENAI_API_KEY,
    )
    self._cleanup_service = cleanup_service or CleanupService()
    self._text_chunk_export_service = text_chunk_export_service or TextChunkExportService(
      chunk_size=DEFAULT_CHUNK_SIZE,
      chunk_overlap=DEFAULT_CHUNK_OVERLAP,
      encoding_name=DEFAULT_ENCODING_NAME,
      semantic_embedding_model=DEFAULT_OPENAI_EMBEDDING_MODEL,
      api_key=settings.OPENAI_API_KEY,
    )
    self._chunk_file_loader_service = chunk_file_loader_service or ChunkFileLoaderService()
    self._chunk_persistence_service = chunk_persistence_service or KnowledgeChunkPersistenceService(
      embedding_service=embedding_service,
    )
    self._parse_service_factory = parse_service_factory or self._default_parse_service_factory
    self._backend_url = backend_url

  # ================================================================================================
  # 소스 처리 실행
  # ------------------------------------------------------------------------------------------------
  # odlh 파이프라인으로 산출물을 만들고 공통 계층으로 임베딩/DB 저장까지 수행합니다
  # ================================================================================================
  def process_source(self, session: Session, source_id: UUID) -> None:
    source = session.exec(select(KnowledgeSourcesModel).where(KnowledgeSourcesModel.id == source_id)).first()
    if not source:
      raise ValueError("처리할 knowledge source를 찾을 수 없습니다.")

    start_time = time.perf_counter()
    logger.info(
      "odlh knowledge source 처리를 시작합니다. source_id=%s display_name=%s storage_path=%s",
      source.id,
      source.display_name,
      source.storage_path,
    )

    try:
      upload_path = self._resolve_upload_path(source)
      paths, markdown, document_json = self._build_pipeline_outputs(source.id, upload_path)
      source_metadata = KnowledgeMetadataService.build(markdown, document_json)
      chunks = self._chunk_file_loader_service.load(paths.json_chunk_output_dir)
      source.token_count = self._chunk_persistence_service.embed_and_replace_chunks(session, source, chunks)
      source.source_metadata = source_metadata.model_dump()
      source.processing_status = ProcessingStatus.DONE
      source.processing_error_message = None
      source.processing_completed_at = datetime.now(UTC)
      source.updated_at = datetime.now(UTC)
      session.add(source)
      session.commit()
      self._cleanup_service.remove_intermediate_artifacts(paths)
      logger.info(
        "odlh knowledge source 처리가 완료되었습니다. source_id=%s chunks=%s token_count=%s elapsed_ms=%s",
        source.id,
        len(chunks),
        source.token_count,
        round((time.perf_counter() - start_time) * 1000, 2),
      )
    except Exception as exc:
      session.rollback()
      logger.exception(
        "odlh knowledge source 처리에 실패했습니다. source_id=%s display_name=%s elapsed_ms=%s error=%s",
        source.id,
        source.display_name,
        round((time.perf_counter() - start_time) * 1000, 2),
        str(exc),
      )
      self._mark_error(session, source_id, str(exc))
      raise

  # ================================================================================================
  # 업로드 파일 경로 계산
  # ------------------------------------------------------------------------------------------------
  # storage_path를 기준으로 실제 업로드 파일의 절대 경로를 계산합니다
  # ================================================================================================
  def _resolve_upload_path(self, source: KnowledgeSourcesModel) -> Path:
    upload_path = Path(settings.UPLOAD_DIR).resolve() / source.storage_path
    if not upload_path.exists():
      raise ValueError(f"업로드 파일을 찾을 수 없습니다: {upload_path}")
    return upload_path

  # ================================================================================================
  # 파이프라인 산출물 생성
  # ------------------------------------------------------------------------------------------------
  # 파일 형식에 따라 odlh 기반 PDF 경로 또는 텍스트 경로로 분기합니다
  # ================================================================================================
  def _build_pipeline_outputs(self, source_id: UUID, upload_path: Path) -> tuple[PipelinePaths, str, dict]:
    output_root = Path(settings.RAG_PDF_OUTPUT_DIR).resolve() / str(source_id)
    suffix = upload_path.suffix.lower()

    if suffix == ".pdf":
      return self._build_pdf_outputs(upload_path, output_root)

    if suffix in self._DIRECT_TEXT_EXTENSIONS:
      return self._build_text_outputs(upload_path, output_root)

    raise ValueError(f"아직 지원하지 않는 knowledge 파일 형식입니다: {suffix}")

  # ================================================================================================
  # PDF 산출물 생성
  # ------------------------------------------------------------------------------------------------
  # Parse -> Analysis -> Chunk 흐름을 수행하고 metadata 입력값을 반환합니다
  # ================================================================================================
  def _build_pdf_outputs(self, upload_path: Path, output_root: Path) -> tuple[PipelinePaths, str, dict]:
    EnvService(backend_url=self._backend_url, api_key=settings.OPENAI_API_KEY).ensure_backend_available()
    parse_service = self._parse_service_factory(output_root, self._backend_url)
    paths = parse_service.convert(upload_path)
    markdown = paths.markdown_path.read_text(encoding="utf-8")
    document_json = read_doc(paths.doc_path)

    self._cleanup_service.prepare_image_output_dir(paths)
    chunking_plan = self._analysis_service.analyze(paths.markdown_path, output_dir=paths.output_dir)
    self._chunk_service.chunk(document_json, paths, chunking_plan.selected_strategy)
    return paths, markdown, document_json

  # ================================================================================================
  # 텍스트 산출물 생성
  # ------------------------------------------------------------------------------------------------
  # Markdown/TXT 파일을 읽어 odlh 스타일 chunks/*.json 산출물로 변환합니다
  # ================================================================================================
  def _build_text_outputs(self, upload_path: Path, output_root: Path) -> tuple[PipelinePaths, str, dict]:
    parsed_document = KnowledgeTextSourceService.read(upload_path)
    paths = resolve_pipeline_paths(upload_path, output_root)

    self._cleanup_service.clear_previous_outputs(paths)
    paths.output_dir.mkdir(parents=True, exist_ok=True)
    paths.markdown_path.write_text(parsed_document.markdown, encoding="utf-8")
    self._cleanup_service.prepare_image_output_dir(paths)

    chunking_plan = self._analysis_service.analyze(paths.markdown_path, output_dir=paths.output_dir)
    self._text_chunk_export_service.export(parsed_document.markdown, paths, chunking_plan.selected_strategy)
    return paths, parsed_document.markdown, parsed_document.document_json

  # ================================================================================================
  # 기본 ParseService 팩토리
  # ------------------------------------------------------------------------------------------------
  # source별 출력 루트를 사용하는 표준 ParseService 인스턴스를 생성합니다
  # ================================================================================================
  def _default_parse_service_factory(self, output_dir: Path, backend_url: str) -> ParseServiceProtocol:
    return ParseService(output_dir=output_dir, backend_url=backend_url)

  # ================================================================================================
  # 오류 상태 기록
  # ------------------------------------------------------------------------------------------------
  # 처리 실패 시 source 상태를 ERROR로 갱신합니다
  # ================================================================================================
  def _mark_error(self, session: Session, source_id: UUID, error_message: str) -> None:
    source = session.exec(select(KnowledgeSourcesModel).where(KnowledgeSourcesModel.id == source_id)).first()
    if not source:
      return

    source.processing_status = ProcessingStatus.ERROR
    source.processing_error_message = error_message
    source.processing_completed_at = datetime.now(UTC)
    source.updated_at = datetime.now(UTC)
    session.add(source)
    session.commit()
