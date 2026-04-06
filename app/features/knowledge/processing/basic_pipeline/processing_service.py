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
from app.features.knowledge.common.knowledge_entity import ParsedDocument
from app.features.knowledge.common.metadata_service import KnowledgeMetadataService
from app.features.knowledge.common.text_source_service import KnowledgeTextSourceService
from app.features.knowledge.processing.basic_pipeline.chunking_service import MarkdownChunkingService
from app.features.knowledge.processing.basic_pipeline.knowledge_parser_adapter import KnowledgeParserAdapter
from app.infrastructure.models.knowledge_model import KnowledgeSourcesModel
from app.infrastructure.models.knowledge_model import ProcessingStatus

logger = logging.getLogger(__name__)


# ==================================================================================================
# 지식 파서 게이트웨이 인터페이스
# --------------------------------------------------------------------------------------------------
# 지식 문서 파서가 구현해야 하는 필수 인터페이스를 정의한 추상 클래스입니다
# ==================================================================================================
class KnowledgeParserGateway(Protocol):
  # ================================================================================================
  # 문서 변환
  # ------------------------------------------------------------------------------------------------
  # 원본 문서를 처리 가능한 중간 형식으로 변환합니다
  # ================================================================================================
  def convert(self, file_path: Path, output_dir: Path) -> ParsedDocument: ...


# ==================================================================================================
# 지식 처리 서비스
# --------------------------------------------------------------------------------------------------
# 문서의 변환부터 청크 생성 및 저장까지의 전체 파이프라인을 관리합니다
# ==================================================================================================
class KnowledgeProcessingService:
  _DIRECT_TEXT_EXTENSIONS: ClassVar[frozenset[str]] = frozenset({".md", ".txt"})

  # ================================================================================================
  # 초기화
  # ------------------------------------------------------------------------------------------------
  # 필요한 의존성 서비스를 주입받아 처리 서비스를 준비합니다
  # ================================================================================================
  def __init__(
    self,
    embedding_service: ChunkEmbeddingGateway,
    parser_adapter: KnowledgeParserGateway | None = None,
    chunking_service: MarkdownChunkingService | None = None,
    chunk_persistence_service: KnowledgeChunkPersistenceService | None = None,
  ):
    self._parser_adapter = parser_adapter or KnowledgeParserAdapter()
    self._chunking_service = chunking_service or MarkdownChunkingService()
    self._chunk_persistence_service = chunk_persistence_service or KnowledgeChunkPersistenceService(
      embedding_service=embedding_service,
    )

  # ================================================================================================
  # 소스 처리 실행
  # ------------------------------------------------------------------------------------------------
  # 할당된 단일 소스 문서에 대해 전체 처리 공정을 수행하고 상태를 갱신합니다
  # ================================================================================================
  def process_source(self, session: Session, source_id: UUID) -> None:
    source = session.exec(select(KnowledgeSourcesModel).where(KnowledgeSourcesModel.id == source_id)).first()
    if not source:
      raise ValueError("처리할 knowledge source를 찾을 수 없습니다.")

    start_time = time.perf_counter()
    logger.info(
      "knowledge source 처리를 시작합니다. source_id=%s display_name=%s storage_path=%s",
      source.id,
      source.display_name,
      source.storage_path,
    )

    try:
      parsed_document = self._parse_source(source)
      source_metadata = KnowledgeMetadataService.build(parsed_document.markdown, parsed_document.document_json)
      chunks = self._chunking_service.chunk(parsed_document.markdown)
      source.token_count = self._chunk_persistence_service.embed_and_replace_chunks(session, source, chunks)
      source.source_metadata = source_metadata.model_dump()
      source.processing_status = ProcessingStatus.DONE
      source.processing_error_message = None
      source.processing_completed_at = datetime.now(UTC)
      source.updated_at = datetime.now(UTC)
      session.add(source)
      session.commit()
      logger.info(
        "knowledge source 처리가 완료되었습니다. source_id=%s chunks=%s token_count=%s elapsed_ms=%s",
        source.id,
        len(chunks),
        source.token_count,
        round((time.perf_counter() - start_time) * 1000, 2),
      )
    except Exception as exc:
      session.rollback()
      logger.exception(
        "knowledge source 처리에 실패했습니다. source_id=%s display_name=%s elapsed_ms=%s error=%s",
        source.id,
        source.display_name,
        round((time.perf_counter() - start_time) * 1000, 2),
        str(exc),
      )
      self._mark_error(session, source_id, str(exc))
      raise

  # ================================================================================================
  # 소스 파싱
  # ------------------------------------------------------------------------------------------------
  # 문서 유형에 맞는 파서를 선택하여 텍스트를 추출합니다
  # ================================================================================================
  def _parse_source(self, source: KnowledgeSourcesModel) -> ParsedDocument:
    upload_path = Path(settings.UPLOAD_DIR).resolve() / source.storage_path
    if not upload_path.exists():
      raise ValueError(f"업로드 파일을 찾을 수 없습니다: {upload_path}")

    if upload_path.suffix.lower() in self._DIRECT_TEXT_EXTENSIONS:
      return self._read_text_source(upload_path)

    if upload_path.suffix.lower() != ".pdf":
      raise ValueError(f"아직 지원하지 않는 knowledge 파일 형식입니다: {upload_path.suffix.lower()}")

    output_dir = Path(settings.RAG_PDF_OUTPUT_DIR).resolve() / str(source.id)
    return self._parser_adapter.convert(upload_path, output_dir)

  # ================================================================================================
  # 텍스트 소스 읽기
  # ------------------------------------------------------------------------------------------------
  # Markdown이나 TXT 파일의 내용을 변환 없이 직접 읽어옵니다
  # ================================================================================================
  def _read_text_source(self, upload_path: Path) -> ParsedDocument:
    return KnowledgeTextSourceService.read(upload_path)

  # ================================================================================================
  # 오류 상태 기록
  # ------------------------------------------------------------------------------------------------
  # 처리 중 발생한 예외 상황을 기록하고 문서 상태를 오류로 변경합니다
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
