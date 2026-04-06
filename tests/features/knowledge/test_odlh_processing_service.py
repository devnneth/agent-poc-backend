from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.features.knowledge.common.knowledge_entity import DocumentChunk
from app.features.knowledge.common.knowledge_entity import ImageReference
from app.features.knowledge.common.knowledge_entity import SourceMetadata
from app.features.knowledge.processing.odlh_pipeline.models.models import PipelinePaths
from app.features.knowledge.processing.odlh_pipeline.processing_service import KnowledgeProcessingService
from app.infrastructure.models.knowledge_model import KnowledgeSourcesModel
from app.infrastructure.models.knowledge_model import ProcessingStatus
from app.infrastructure.models.knowledge_model import SourceType


# ==================================================================================================
# 더미 임베딩 서비스
# --------------------------------------------------------------------------------------------------
# 기본 생성자 시그니처를 맞추기 위한 최소 임베딩 게이트웨이 구현입니다
# ==================================================================================================
class DummyEmbeddingService:
  async def embedding(self, texts: list[str]) -> list[list[float]]:
    return [[0.1] * 1536 for _ in texts]


# ==================================================================================================
# 청크 로더 테스트
# --------------------------------------------------------------------------------------------------
# odlh 청크 파일 로더가 파일명 순서대로 DocumentChunk를 읽는지 검증합니다
# ==================================================================================================
def test_odlh_chunk_file_loader_reads_chunks_in_filename_order(tmp_path):
  from app.features.knowledge.processing.odlh_pipeline.services.chunk_file_loader_service import ChunkFileLoaderService

  chunk_dir = tmp_path / "chunks"
  chunk_dir.mkdir(parents=True, exist_ok=True)
  (chunk_dir / "_manifest.json").write_text("[]", encoding="utf-8")
  (chunk_dir / "002_beta_001.json").write_text(
    json.dumps({"content": "두 번째", "metadata": {"title": "beta"}}, ensure_ascii=False),
    encoding="utf-8",
  )
  (chunk_dir / "001_alpha_001.json").write_text(
    json.dumps({"content": "첫 번째", "metadata": {"title": "alpha"}}, ensure_ascii=False),
    encoding="utf-8",
  )

  chunks = ChunkFileLoaderService().load(chunk_dir)

  assert [chunk.chunk_index for chunk in chunks] == [0, 1]
  assert [chunk.content for chunk in chunks] == ["첫 번째", "두 번째"]
  assert chunks[0].metadata_payload() == {"title": "alpha"}
  assert chunks[1].metadata_payload() == {"title": "beta"}


# ==================================================================================================
# odlh 텍스트 처리 경로 테스트
# --------------------------------------------------------------------------------------------------
# Markdown/TXT 파일도 odlh 모듈 내부 경로로 처리되어 공통 persistence까지 연결되는지 검증합니다
# ==================================================================================================
def test_odlh_processing_service_handles_markdown_source_with_odlh_flow(tmp_path, monkeypatch):
  analysis_service = MagicMock()
  analysis_service.analyze.return_value = MagicMock(selected_strategy="hybrid")
  cleanup_service = MagicMock()
  text_chunk_export_service = MagicMock()
  chunk_file_loader_service = MagicMock(
    load=MagicMock(
      return_value=[
        DocumentChunk(chunk_index=0, content="첫 번째 청크", metadata={"title": "첫 번째"}),
        DocumentChunk(chunk_index=1, content="두 번째 청크", metadata={"title": "두 번째"}),
      ]
    )
  )
  chunk_persistence_service = MagicMock(embed_and_replace_chunks=MagicMock(return_value=7))
  service = KnowledgeProcessingService(
    embedding_service=DummyEmbeddingService(),
    analysis_service=analysis_service,
    cleanup_service=cleanup_service,
    text_chunk_export_service=text_chunk_export_service,
    chunk_file_loader_service=chunk_file_loader_service,
    chunk_persistence_service=chunk_persistence_service,
  )
  monkeypatch.setattr(
    "app.features.knowledge.processing.odlh_pipeline.processing_service.KnowledgeMetadataService.build",
    MagicMock(
      return_value=SourceMetadata(
        topic_keywords=["제목", "본문", "도표", "마크다운", "청크"],
        description="Markdown source 메타데이터",
        parser="opendataloader-pdf",
        content_format="markdown",
        has_images=True,
        image_references=[ImageReference(alt_text="도표", path="./images/a.png")],
      )
    ),
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
  file_path.write_text("# 제목\n\n![도표](./images/a.png)\n\n본문 내용입니다.\n", encoding="utf-8")
  monkeypatch.setattr("app.features.knowledge.processing.odlh_pipeline.processing_service.settings._settings.UPLOAD_DIR", str(upload_dir))
  monkeypatch.setattr(
    "app.features.knowledge.processing.odlh_pipeline.processing_service.settings._settings.RAG_PDF_OUTPUT_DIR",
    str(tmp_path / ".odlh"),
  )

  session = MagicMock()
  session.exec.side_effect = [MagicMock(first=MagicMock(return_value=source)), MagicMock()]

  service.process_source(session, source_id)

  analysis_service.analyze.assert_called_once()
  text_chunk_export_service.export.assert_called_once()
  chunk_file_loader_service.load.assert_called_once()
  chunk_persistence_service.embed_and_replace_chunks.assert_called_once()
  assert source.processing_status == ProcessingStatus.DONE
  assert source.token_count == 7
  assert source.source_metadata is not None
  assert source.source_metadata["has_images"] is True


# ==================================================================================================
# odlh PDF 처리 경로 테스트
# --------------------------------------------------------------------------------------------------
# PDF source는 parse/analyze/chunk 후 공통 persistence 계층으로 연결되는지 검증합니다
# ==================================================================================================
def test_odlh_processing_service_handles_pdf_source_with_odlh_flow(tmp_path, monkeypatch):
  analysis_service = MagicMock()
  analysis_service.analyze.return_value = MagicMock(selected_strategy="hybrid")
  chunk_service = MagicMock()
  cleanup_service = MagicMock()
  chunk_file_loader_service = MagicMock(load=MagicMock(return_value=[DocumentChunk(chunk_index=0, content="PDF 청크", metadata={"title": "제목"})]))
  chunk_persistence_service = MagicMock(embed_and_replace_chunks=MagicMock(return_value=3))

  output_root = tmp_path / ".odlh"
  expected_paths = PipelinePaths(
    pdf_path=(tmp_path / "uploads" / "user-123" / "doc.pdf").resolve(),
    output_dir=output_root / "doc",
    doc_path=output_root / "doc" / "doc.json",
    markdown_path=output_root / "doc" / "doc.md",
    markdown_output_dir=output_root / "doc" / "markdowns",
    json_chunk_output_dir=output_root / "doc" / "chunks",
    image_output_dir=output_root / "doc" / "images",
    raw_image_output_dir=output_root / "doc" / "doc_images",
  )

  class FakeParseService:
    def convert(self, pdf_path: str | Path) -> PipelinePaths:
      del pdf_path
      expected_paths.output_dir.mkdir(parents=True, exist_ok=True)
      expected_paths.doc_path.write_text(json.dumps({"kids": [{"id": 1, "type": "heading", "content": "제목"}]}), encoding="utf-8")
      expected_paths.markdown_path.write_text("# 제목\n\n본문\n", encoding="utf-8")
      return expected_paths

  def fake_parse_service_factory(output_dir: Path, backend_url: str) -> FakeParseService:
    del output_dir, backend_url
    return FakeParseService()

  service = KnowledgeProcessingService(
    embedding_service=DummyEmbeddingService(),
    analysis_service=analysis_service,
    chunk_service=chunk_service,
    cleanup_service=cleanup_service,
    chunk_file_loader_service=chunk_file_loader_service,
    chunk_persistence_service=chunk_persistence_service,
    parse_service_factory=fake_parse_service_factory,
  )
  backend_env_service = MagicMock()
  backend_env_service_class = MagicMock(return_value=backend_env_service)
  monkeypatch.setattr(
    "app.features.knowledge.processing.odlh_pipeline.processing_service.EnvService",
    backend_env_service_class,
  )
  monkeypatch.setattr(
    "app.features.knowledge.processing.odlh_pipeline.processing_service.KnowledgeMetadataService.build",
    MagicMock(
      return_value=SourceMetadata(
        topic_keywords=["제목", "본문", "pdf", "청크", "문서"],
        description="PDF source 메타데이터",
        parser="opendataloader-pdf",
        content_format="markdown",
        page_count=1,
      )
    ),
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
  monkeypatch.setattr("app.features.knowledge.processing.odlh_pipeline.processing_service.settings._settings.UPLOAD_DIR", str(upload_dir))
  monkeypatch.setattr(
    "app.features.knowledge.processing.odlh_pipeline.processing_service.settings._settings.RAG_PDF_OUTPUT_DIR",
    str(output_root),
  )

  session = MagicMock()
  session.exec.side_effect = [MagicMock(first=MagicMock(return_value=source)), MagicMock()]

  service.process_source(session, source_id)

  backend_env_service_class.assert_called_once_with(backend_url="http://127.0.0.1:5002")
  backend_env_service.ensure_backend_available.assert_called_once_with()
  analysis_service.analyze.assert_called_once_with(expected_paths.markdown_path, output_dir=expected_paths.output_dir)
  chunk_service.chunk.assert_called_once()
  chunk_file_loader_service.load.assert_called_once_with(expected_paths.json_chunk_output_dir)
  chunk_persistence_service.embed_and_replace_chunks.assert_called_once()
  cleanup_service.prepare_image_output_dir.assert_called_once_with(expected_paths)
  cleanup_service.remove_intermediate_artifacts.assert_called_once_with(expected_paths)
  assert source.processing_status == ProcessingStatus.DONE
  assert source.token_count == 3


# ==================================================================================================
# odlh 미지원 확장자 오류 테스트
# --------------------------------------------------------------------------------------------------
# odlh 모듈도 지원하지 않는 확장자에 대해 명시적 오류를 기록하는지 검증합니다
# ==================================================================================================
def test_odlh_processing_service_marks_unsupported_extension_as_error(tmp_path, monkeypatch):
  service = KnowledgeProcessingService(embedding_service=DummyEmbeddingService())
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
  monkeypatch.setattr("app.features.knowledge.processing.odlh_pipeline.processing_service.settings._settings.UPLOAD_DIR", str(upload_dir))

  session = MagicMock()
  session.exec.side_effect = [
    MagicMock(first=MagicMock(return_value=source)),
    MagicMock(first=MagicMock(return_value=error_marked_source)),
  ]

  with pytest.raises(ValueError, match="지원하지 않는 knowledge 파일 형식"):
    service.process_source(session, source_id)

  assert error_marked_source.processing_status == ProcessingStatus.ERROR


# ==================================================================================================
# odlh PDF 백엔드 미가동 오류 테스트
# --------------------------------------------------------------------------------------------------
# PDF 처리 직전 backend check가 실패하면 parse 단계로 가지 않고 source를 ERROR로 기록하는지 검증합니다
# ==================================================================================================
def test_odlh_processing_service_marks_pdf_source_as_error_when_backend_is_unavailable(tmp_path, monkeypatch):
  parse_service_factory = MagicMock()
  service = KnowledgeProcessingService(
    embedding_service=DummyEmbeddingService(),
    parse_service_factory=parse_service_factory,
  )

  backend_env_service = MagicMock()
  backend_env_service.ensure_backend_available.side_effect = ValueError("백엔드 접근 실패")
  backend_env_service_class = MagicMock(return_value=backend_env_service)
  monkeypatch.setattr(
    "app.features.knowledge.processing.odlh_pipeline.processing_service.EnvService",
    backend_env_service_class,
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
  error_marked_source = KnowledgeSourcesModel.model_validate(source.model_dump())

  upload_dir = tmp_path / "uploads"
  file_path = upload_dir / "user-123" / "doc.pdf"
  file_path.parent.mkdir(parents=True, exist_ok=True)
  file_path.write_bytes(b"pdf")
  monkeypatch.setattr("app.features.knowledge.processing.odlh_pipeline.processing_service.settings._settings.UPLOAD_DIR", str(upload_dir))

  session = MagicMock()
  session.exec.side_effect = [
    MagicMock(first=MagicMock(return_value=source)),
    MagicMock(first=MagicMock(return_value=error_marked_source)),
  ]

  with pytest.raises(ValueError, match="백엔드 접근 실패"):
    service.process_source(session, source_id)

  backend_env_service_class.assert_called_once_with(backend_url="http://127.0.0.1:5002")
  backend_env_service.ensure_backend_available.assert_called_once_with()
  parse_service_factory.assert_not_called()
  assert error_marked_source.processing_status == ProcessingStatus.ERROR
