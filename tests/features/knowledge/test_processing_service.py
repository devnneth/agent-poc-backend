from __future__ import annotations

from pathlib import Path
from typing import Any
from typing import cast
from unittest.mock import MagicMock
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import NoReferencedTableError

from app.features.knowledge.common.knowledge_entity import ChunkMetadata
from app.features.knowledge.common.knowledge_entity import ParsedDocument
from app.features.knowledge.common.metadata_service import KnowledgeMetadataService
from app.features.knowledge.processing.basic_pipeline.chunking_service import MarkdownChunkingService
from app.features.knowledge.processing.basic_pipeline.processing_service import KnowledgeProcessingService
from app.features.knowledge.processing.worker import KnowledgeProcessingWorker
from app.infrastructure.models.knowledge_model import KnowledgeSourcesModel
from app.infrastructure.models.knowledge_model import ProcessingStatus
from app.infrastructure.models.knowledge_model import SourceType


# ==================================================================================================
# 모의 임베딩 서비스
# --------------------------------------------------------------------------------------------------
# 테스트용 배치 임베딩 결과를 생성하는 가짜 서비스 클래스
# ==================================================================================================
class FakeEmbeddingService:
  # ================================================================================================
  # 모의 임베딩 생성
  # ------------------------------------------------------------------------------------------------
  # 요청된 개수만큼의 가짜 벡터를 생성하여 반환
  # ================================================================================================
  async def embedding(self, texts: list[str]) -> list[list[float]]:
    return [[0.1] * 1536 for _ in texts]


# ==================================================================================================
# 모의 PDF 어댑터
# --------------------------------------------------------------------------------------------------
# CLI 호출 대신 미리 정의된 변환 결과를 반환하는 가짜 어댑터 클래스
# ==================================================================================================
class FakePdfAdapter:
  # ================================================================================================
  # PDF 어댑터 초기화
  # ------------------------------------------------------------------------------------------------
  # 모의 어댑터의 상태를 초기화
  # ================================================================================================
  def __init__(self, parsed_document: ParsedDocument):
    self._parsed_document = parsed_document
    self.last_output_dir: Path | None = None

  # ================================================================================================
  # PDF 변환 모의 실행
  # ------------------------------------------------------------------------------------------------
  # 실제 변환 과정 없이 고정된 결과물을 생성
  # ================================================================================================
  def convert(self, file_path: Path, output_dir: Path) -> ParsedDocument:
    self.last_output_dir = output_dir
    return self._parsed_document


# ==================================================================================================
# 본문 기반 메타데이터 생성 테스트
# --------------------------------------------------------------------------------------------------
# 청크 본문을 분석하여 키워드와 설명을 올바르게 생성하는지 검증
# ==================================================================================================
def test_metadata_service_builds_content_based_metadata():
  markdown = """# RAG 개요

RAG 시스템은 검색과 생성 단계를 결합합니다.

## 임베딩

임베딩 파이프라인은 문서를 청킹하고 벡터를 생성합니다.
"""
  metadata = KnowledgeMetadataService.build(markdown, {"pages": [{"number": 1}]})

  assert len(metadata.topic_keywords) == 5
  assert metadata.parser == "opendataloader-pdf"
  assert metadata.content_format == "markdown"
  assert metadata.page_count == 1
  assert metadata.image_references == []


# ==================================================================================================
# LLM 토픽 키워드 활용 테스트
# --------------------------------------------------------------------------------------------------
# LLM 응답이 있을 때 추출된 토픽 키워드를 우선 사용하는지 검증
# ==================================================================================================
def test_metadata_service_uses_llm_keywords_when_available():
  markdown = """# RAG 개요

RAG 시스템은 검색과 생성 단계를 결합합니다.

## 임베딩

임베딩 파이프라인은 문서를 청킹하고 벡터를 생성합니다.
  """
  mock_service = MagicMock()
  mock_service.get_topic_keywords.return_value = ["rag", "임베딩", "청킹", "검색", "생성"]
  mock_service.chunk_summary.return_value = "RAG와 임베딩 흐름을 요약한 문서입니다."

  with patch("app.features.knowledge.common.metadata_service.LLMServiceFactory.get_service", return_value=mock_service):
    metadata = KnowledgeMetadataService.build(markdown, {"pages": [{"number": 1}]})

  assert metadata.topic_keywords == ["rag", "임베딩", "청킹", "검색", "생성"]
  mock_service.get_topic_keywords.assert_called_once()


# ==================================================================================================
# LLM 청크 요약 활용 테스트
# --------------------------------------------------------------------------------------------------
# LLM 요약 결과가 청크 설명에 올바르게 반영되는지 검증
# ==================================================================================================
def test_metadata_service_uses_llm_chunk_summary_for_description():
  markdown = """# RAG 개요

RAG 시스템은 검색과 생성 단계를 결합합니다.

## 임베딩

임베딩 파이프라인은 문서를 청킹하고 벡터를 생성합니다.
"""
  mock_service = MagicMock()
  mock_service.get_topic_keywords.return_value = ["rag", "임베딩", "청킹", "검색", "생성"]
  mock_service.chunk_summary.return_value = "RAG와 임베딩 파이프라인의 핵심 흐름을 설명하는 문서입니다."

  with patch("app.features.knowledge.common.metadata_service.LLMServiceFactory.get_service", return_value=mock_service):
    metadata = KnowledgeMetadataService.build(markdown, {"pages": [{"number": 1}]})

  assert metadata.description == "RAG와 임베딩 파이프라인의 핵심 흐름을 설명하는 문서입니다."
  mock_service.chunk_summary.assert_called_once()


# ==================================================================================================
# LLM 실패 시 키워드 폴백 테스트
# --------------------------------------------------------------------------------------------------
# LLM 추출 실패 시 규칙 기반 키워드 추출로 정상 전환되는지 검증
# ==================================================================================================
def test_metadata_service_falls_back_to_rule_based_keywords_when_llm_fails():
  markdown = """# RAG 개요

RAG 시스템은 검색과 생성 단계를 결합합니다.

## 임베딩

임베딩 파이프라인은 문서를 청킹하고 벡터를 생성합니다.
  """
  mock_service = MagicMock()
  mock_service.get_topic_keywords.side_effect = RuntimeError("llm unavailable")
  mock_service.chunk_summary.return_value = "RAG와 임베딩 흐름을 요약한 문서입니다."

  with patch("app.features.knowledge.common.metadata_service.LLMServiceFactory.get_service", return_value=mock_service):
    metadata = KnowledgeMetadataService.build(markdown, {"pages": [{"number": 1}]})

  assert len(metadata.topic_keywords) == 5
  assert metadata.topic_keywords[0] == "rag"
  assert "임베딩" in metadata.topic_keywords


# ==================================================================================================
# LLM 실패 시 설명 폴백 테스트
# --------------------------------------------------------------------------------------------------
# LLM 요약 실패 시 규칙 기반 설명 생성으로 정상 전환되는지 검증
# ==================================================================================================
def test_metadata_service_falls_back_to_rule_based_description_when_llm_summary_fails():
  markdown = """# RAG 개요

RAG 시스템은 검색과 생성 단계를 결합합니다.

## 임베딩

임베딩 파이프라인은 문서를 청킹하고 벡터를 생성합니다.
"""
  mock_service = MagicMock()
  mock_service.get_topic_keywords.return_value = ["rag", "임베딩", "청킹", "검색", "생성"]
  mock_service.chunk_summary.side_effect = RuntimeError("summary unavailable")

  with patch("app.features.knowledge.common.metadata_service.LLMServiceFactory.get_service", return_value=mock_service):
    metadata = KnowledgeMetadataService.build(markdown, {"pages": [{"number": 1}]})

  assert metadata.description == "RAG 개요 RAG 시스템은 검색과 생성 단계를 결합합니다."


# ==================================================================================================
# 짧은 문서 키워드 허용 테스트
# --------------------------------------------------------------------------------------------------
# 본문이 짧아 LLM이 5개 미만 키워드를 반환해도 메타데이터 생성이 실패하지 않는지 검증
# ==================================================================================================
def test_metadata_service_allows_short_llm_keyword_results():
  markdown = "# 제목\n\n본문"
  mock_service = MagicMock()
  mock_service.get_topic_keywords.return_value = ["제목", "본문"]
  mock_service.chunk_summary.return_value = "짧은 문서를 설명하는 메타데이터입니다."

  with patch("app.features.knowledge.common.metadata_service.LLMServiceFactory.get_service", return_value=mock_service):
    metadata = KnowledgeMetadataService.build(markdown, {"pages": [{"number": 1}]})

  assert metadata.topic_keywords == ["제목", "본문"]
  assert metadata.description == "짧은 문서를 설명하는 메타데이터입니다."


# ==================================================================================================
# 키워드 없음 허용 테스트
# --------------------------------------------------------------------------------------------------
# 규칙 기반 추출 결과가 비어도 메타데이터 생성이 실패하지 않는지 검증
# ==================================================================================================
def test_metadata_service_allows_empty_keywords_for_tiny_document():
  markdown = "# 가"
  mock_service = MagicMock()
  mock_service.get_topic_keywords.side_effect = RuntimeError("llm unavailable")
  mock_service.chunk_summary.side_effect = RuntimeError("summary unavailable")

  with patch("app.features.knowledge.common.metadata_service.LLMServiceFactory.get_service", return_value=mock_service):
    metadata = KnowledgeMetadataService.build(markdown, {"pages": [{"number": 1}]})

  assert metadata.topic_keywords == []
  assert metadata.description == "이 문서의 주요 내용은 가 입니다."


# ==================================================================================================
# Markdown 헤더 경로 보존 테스트
# --------------------------------------------------------------------------------------------------
# 청킹 과정에서 헤더 경로가 메타데이터에 정확히 기록되는지 검증
# ==================================================================================================
def test_markdown_chunking_service_preserves_heading_path():
  markdown = """# 첫 제목

첫 문단입니다.

## 두 번째 제목

- 목록 항목 하나
- 목록 항목 둘
"""
  service = MarkdownChunkingService(max_chunk_chars=200)

  chunks = service.chunk(markdown)

  assert len(chunks) == 2
  assert isinstance(chunks[0].metadata, ChunkMetadata)
  assert isinstance(chunks[1].metadata, ChunkMetadata)
  assert chunks[0].metadata.heading_path == ["첫 제목"]
  assert chunks[1].metadata.heading_path == ["첫 제목", "두 번째 제목"]


# ==================================================================================================
# 처리 완료 상태 기록 테스트
# --------------------------------------------------------------------------------------------------
# 지식 처리가 정상 종료된 후 DONE 상태와 메타데이터가 저장되는지 검증
# ==================================================================================================
def test_processing_service_marks_source_done(tmp_path, monkeypatch):
  markdown = """# 문서 제목

문서 본문은 RAG 처리와 임베딩 생성 과정을 설명합니다.

## 상세 섹션

추가 내용이 이어집니다.
"""
  parsed_document = ParsedDocument(markdown=markdown, document_json={"pages": [{"number": 1}]})
  parser_adapter = FakePdfAdapter(parsed_document)
  embedding_service = FakeEmbeddingService()
  service = KnowledgeProcessingService(
    embedding_service=embedding_service,
    parser_adapter=parser_adapter,
    chunking_service=MarkdownChunkingService(max_chunk_chars=200),
  )

  source_id = uuid4()
  source = KnowledgeSourcesModel(
    id=source_id,
    knowledge_id=uuid4(),
    user_id="user-123",
    source_type=SourceType.FILE,
    display_name="doc.pdf",
    storage_path="user-123/doc.pdf",
    processing_status=ProcessingStatus.ING,
  )

  upload_dir = tmp_path / "uploads"
  file_path = upload_dir / "user-123" / "doc.pdf"
  file_path.parent.mkdir(parents=True, exist_ok=True)
  file_path.write_bytes(b"pdf")
  monkeypatch.setattr(
    "app.features.knowledge.processing.basic_pipeline.processing_service.settings._settings.UPLOAD_DIR",
    str(upload_dir),
  )
  rag_output_dir = tmp_path / ".opendataloader"
  monkeypatch.setattr(
    "app.features.knowledge.processing.basic_pipeline.processing_service.settings._settings.RAG_PDF_OUTPUT_DIR",
    str(rag_output_dir),
  )

  session = MagicMock()
  session.exec.side_effect = [MagicMock(first=MagicMock(return_value=source)), MagicMock()]

  service.process_source(session, source_id)

  assert parser_adapter.last_output_dir == rag_output_dir.resolve() / str(source_id)
  assert source.processing_status == ProcessingStatus.DONE
  assert source.processing_error_message is None
  assert source.source_metadata is not None
  assert session.commit.call_count >= 1


# ==================================================================================================
# 처리 시작 및 완료 로그 테스트
# --------------------------------------------------------------------------------------------------
# 지식 처리의 시작과 종료 시점이 로그에 정확히 기록되는지 검증
# ==================================================================================================
def test_processing_service_logs_start_and_completion(tmp_path, monkeypatch, caplog):
  markdown = """# 문서 제목

문서 본문은 RAG 처리와 임베딩 생성 과정을 설명합니다.

## 상세 섹션

추가 내용이 이어집니다.
"""
  parsed_document = ParsedDocument(markdown=markdown, document_json={"pages": [{"number": 1}]})
  parser_adapter = FakePdfAdapter(parsed_document)
  embedding_service = FakeEmbeddingService()
  service = KnowledgeProcessingService(
    embedding_service=embedding_service,
    parser_adapter=parser_adapter,
    chunking_service=MarkdownChunkingService(max_chunk_chars=200),
  )

  source_id = uuid4()
  source = KnowledgeSourcesModel(
    id=source_id,
    knowledge_id=uuid4(),
    user_id="user-123",
    source_type=SourceType.FILE,
    display_name="doc.pdf",
    storage_path="user-123/doc.pdf",
    processing_status=ProcessingStatus.ING,
  )

  upload_dir = tmp_path / "uploads"
  file_path = upload_dir / "user-123" / "doc.pdf"
  file_path.parent.mkdir(parents=True, exist_ok=True)
  file_path.write_bytes(b"pdf")
  monkeypatch.setattr(
    "app.features.knowledge.processing.basic_pipeline.processing_service.settings._settings.UPLOAD_DIR",
    str(upload_dir),
  )
  rag_output_dir = tmp_path / ".opendataloader"
  monkeypatch.setattr(
    "app.features.knowledge.processing.basic_pipeline.processing_service.settings._settings.RAG_PDF_OUTPUT_DIR",
    str(rag_output_dir),
  )

  session = MagicMock()
  session.exec.side_effect = [MagicMock(first=MagicMock(return_value=source)), MagicMock()]

  with patch("app.features.knowledge.processing.basic_pipeline.processing_service.logger") as logger_mock:
    service.process_source(session, source_id)

  assert logger_mock.info.call_count >= 2
  assert "knowledge source 처리를 시작합니다." in logger_mock.info.call_args_list[0].args[0]
  assert "knowledge source 처리가 완료되었습니다." in logger_mock.info.call_args_list[-1].args[0]


# ==================================================================================================
# Markdown 직통 처리 테스트
# --------------------------------------------------------------------------------------------------
# Markdown 파일은 PDF 변환 과정 없이 즉시 처리되는지 검증
# ==================================================================================================
def test_processing_service_reads_markdown_source_without_pdf_conversion(tmp_path, monkeypatch):
  parser_adapter = MagicMock()
  embedding_service = FakeEmbeddingService()
  service = KnowledgeProcessingService(
    embedding_service=embedding_service,
    parser_adapter=parser_adapter,
    chunking_service=MarkdownChunkingService(max_chunk_chars=200),
  )

  source_id = uuid4()
  source = KnowledgeSourcesModel(
    id=source_id,
    knowledge_id=uuid4(),
    user_id="user-123",
    source_type=SourceType.FILE,
    display_name="chapter1.md",
    storage_path="user-123/chapter1.md",
    processing_status=ProcessingStatus.ING,
  )

  upload_dir = tmp_path / "uploads"
  file_path = upload_dir / "user-123" / "chapter1.md"
  file_path.parent.mkdir(parents=True, exist_ok=True)
  file_path.write_text(
    "# 문서 제목\n\n![시스템 구조](./images/arch.png)\n\nRAG 검색 시스템은 문서 청킹 임베딩 검색 생성을 함께 다룹니다.\n",
    encoding="utf-8",
  )
  monkeypatch.setattr(
    "app.features.knowledge.processing.basic_pipeline.processing_service.settings._settings.UPLOAD_DIR",
    str(upload_dir),
  )

  session = MagicMock()
  session.exec.side_effect = [MagicMock(first=MagicMock(return_value=source)), MagicMock()]

  service.process_source(session, source_id)

  parser_adapter.convert.assert_not_called()
  assert source.processing_status == ProcessingStatus.DONE
  assert source.processing_error_message is None
  assert source.source_metadata is not None
  assert source.source_metadata["page_count"] is None
  assert source.source_metadata["has_images"] is True
  assert source.source_metadata["image_references"] == [{"alt_text": "시스템 구조", "path": "./images/arch.png"}]


# ==================================================================================================
# Markdown 이미지 참조 식별 테스트
# --------------------------------------------------------------------------------------------------
# 본문 내 이미지 참조를 메타데이터에 이미지로 표시하는지 검증
# ==================================================================================================
def test_metadata_service_marks_markdown_image_references_as_images():
  markdown = "# 아키텍처\n\n이미지: 시스템 구조\n\n설명 텍스트가 충분히 이어집니다."

  metadata = KnowledgeMetadataService.build(
    markdown,
    {"image_references": [{"alt_text": "시스템 구조", "path": "./images/arch.png"}]},
  )

  assert metadata.has_images is True
  assert [image_reference.model_dump() for image_reference in metadata.image_references] == [{"alt_text": "시스템 구조", "path": "./images/arch.png"}]


# ==================================================================================================
# 처리 실패 상태 기록 테스트
# --------------------------------------------------------------------------------------------------
# 예외 발생 시 ERROR 상태와 상세 오류 메시지가 기록되는지 검증
# ==================================================================================================
def test_processing_service_marks_source_error_on_failure():
  embedding_service = FakeEmbeddingService()
  service = KnowledgeProcessingService(embedding_service=embedding_service)
  source_id = uuid4()
  source = KnowledgeSourcesModel(
    id=source_id,
    knowledge_id=uuid4(),
    user_id="user-123",
    source_type=SourceType.FILE,
    display_name="missing.pdf",
    storage_path="user-123/missing.pdf",
    processing_status=ProcessingStatus.ING,
  )
  error_marked_source = KnowledgeSourcesModel.model_validate(source.model_dump())

  session = MagicMock()
  session.exec.side_effect = [
    MagicMock(first=MagicMock(return_value=source)),
    MagicMock(first=MagicMock(return_value=error_marked_source)),
  ]

  with pytest.raises(ValueError):
    service.process_source(session, source_id)

  assert error_marked_source.processing_status == ProcessingStatus.ERROR
  assert error_marked_source.processing_error_message is not None


# ==================================================================================================
# 처리 실패 로그 테스트
# --------------------------------------------------------------------------------------------------
# 오류 발생 시 상세 로그가 남는지 검증
# ==================================================================================================
def test_processing_service_logs_failure():
  embedding_service = FakeEmbeddingService()
  service = KnowledgeProcessingService(embedding_service=embedding_service)
  source_id = uuid4()
  source = KnowledgeSourcesModel(
    id=source_id,
    knowledge_id=uuid4(),
    user_id="user-123",
    source_type=SourceType.FILE,
    display_name="missing.pdf",
    storage_path="user-123/missing.pdf",
    processing_status=ProcessingStatus.ING,
  )
  error_marked_source = KnowledgeSourcesModel.model_validate(source.model_dump())

  session = MagicMock()
  session.exec.side_effect = [
    MagicMock(first=MagicMock(return_value=source)),
    MagicMock(first=MagicMock(return_value=error_marked_source)),
  ]

  with (
    patch("app.features.knowledge.processing.basic_pipeline.processing_service.logger") as logger_mock,
    pytest.raises(ValueError),
  ):
    service.process_source(session, source_id)

  assert logger_mock.exception.call_count == 1
  assert "knowledge source 처리에 실패했습니다." in logger_mock.exception.call_args.args[0]


# ==================================================================================================
# 미지원 확장자 오류 처리 테스트
# --------------------------------------------------------------------------------------------------
# 지원하지 않는 확장자 파일을 명시적인 오류 상태로 처리하는지 검증
# ==================================================================================================
def test_processing_service_marks_unsupported_extension_as_error(tmp_path, monkeypatch):
  embedding_service = FakeEmbeddingService()
  service = KnowledgeProcessingService(embedding_service=embedding_service)
  source_id = uuid4()
  source = KnowledgeSourcesModel(
    id=source_id,
    knowledge_id=uuid4(),
    user_id="user-123",
    source_type=SourceType.FILE,
    display_name="book.epub",
    storage_path="user-123/book.epub",
    processing_status=ProcessingStatus.ING,
  )
  error_marked_source = KnowledgeSourcesModel.model_validate(source.model_dump())

  upload_dir = tmp_path / "uploads"
  file_path = upload_dir / "user-123" / "book.epub"
  file_path.parent.mkdir(parents=True, exist_ok=True)
  file_path.write_bytes(b"epub")
  monkeypatch.setattr(
    "app.features.knowledge.processing.basic_pipeline.processing_service.settings._settings.UPLOAD_DIR",
    str(upload_dir),
  )

  session = MagicMock()
  session.exec.side_effect = [
    MagicMock(first=MagicMock(return_value=source)),
    MagicMock(first=MagicMock(return_value=error_marked_source)),
  ]

  with pytest.raises(ValueError, match="지원하지 않는 knowledge 파일 형식"):
    service.process_source(session, source_id)

  assert error_marked_source.processing_status == ProcessingStatus.ERROR
  assert error_marked_source.processing_error_message is not None


# ==================================================================================================
# 워커 선점 쿼리 검증
# --------------------------------------------------------------------------------------------------
# 중복 처리를 방지하기 위한 SKIP LOCKED 구문 사용 여부를 검증
# ==================================================================================================
def test_worker_claim_statement_uses_skip_locked():
  sql = KnowledgeProcessingWorker.compile_claim_statement(2)

  assert "FOR UPDATE SKIP LOCKED" in sql


# ==================================================================================================
# 사용자 외래 키 해석 테스트
# --------------------------------------------------------------------------------------------------
# 지식 모델 단독 로드 시에도 auth.users 테이블과의 관계가 해석되는지 검증
# ==================================================================================================
def test_knowledge_source_user_fk_resolves_auth_users_table():
  user_id_column = cast(Any, KnowledgeSourcesModel).__table__.c.user_id
  foreign_key = next(iter(user_id_column.foreign_keys))

  try:
    resolved_column = foreign_key.column
  except NoReferencedTableError as error:
    pytest.fail(f"auth.users 외래 키를 해석하지 못했습니다: {error}")

  assert resolved_column.table.fullname == "auth.users"
  assert resolved_column.name == "id"


# ==================================================================================================
# 워커 선점 상태 전이 테스트
# --------------------------------------------------------------------------------------------------
# 작업 선점 즉시 소스 상태가 ING로 변경되는지 검증
# ==================================================================================================
def test_worker_claim_pending_sources_marks_ing():
  source = KnowledgeSourcesModel(
    id=uuid4(),
    knowledge_id=uuid4(),
    user_id="user-123",
    source_type=SourceType.FILE,
    display_name="doc.pdf",
    storage_path="user-123/doc.pdf",
    processing_status=ProcessingStatus.PENDING,
  )
  session = MagicMock()
  session.exec.return_value.all.return_value = [source]
  worker = KnowledgeProcessingWorker(session_factory=lambda: session, processor=MagicMock(), concurrency=2)

  claimed = worker.claim_pending_sources(session)

  assert len(claimed) == 1
  assert claimed[0].processing_status == ProcessingStatus.ING
  assert claimed[0].processing_started_at is not None
  session.commit.assert_called_once()


# ==================================================================================================
# 개별 소스 실패 격리 테스트
# --------------------------------------------------------------------------------------------------
# 특정 소스 처리 실패가 전체 워커 실행에 영향을 주지 않는지 검증
# ==================================================================================================
def test_worker_run_once_continues_when_single_source_processing_fails():
  source = KnowledgeSourcesModel(
    id=uuid4(),
    knowledge_id=uuid4(),
    user_id="user-123",
    source_type=SourceType.FILE,
    display_name="doc.pdf",
    storage_path="user-123/doc.pdf",
    processing_status=ProcessingStatus.PENDING,
  )
  claim_session = MagicMock()
  claim_session.exec.return_value.all.return_value = [source]
  process_session = MagicMock()

  session_factory = MagicMock()
  session_factory.return_value.__enter__.side_effect = [claim_session, process_session]
  session_factory.return_value.__exit__.return_value = None

  processor = MagicMock()
  processor.process_source.side_effect = ValueError("opendataloader-pdf 명령을 찾을 수 없습니다.")
  worker = KnowledgeProcessingWorker(session_factory=session_factory, processor=processor, concurrency=1)

  processed_count = worker.run_once()

  assert processed_count == 1
  processor.process_source.assert_called_once_with(process_session, source.id)
