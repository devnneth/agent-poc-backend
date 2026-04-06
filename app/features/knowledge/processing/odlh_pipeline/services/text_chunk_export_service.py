from __future__ import annotations

import json
from pathlib import Path

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from app.features.knowledge.processing.odlh_pipeline.config.contants import CHUNK_CONTENT_KEY
from app.features.knowledge.processing.odlh_pipeline.config.contants import CHUNK_METADATA_KEY
from app.features.knowledge.processing.odlh_pipeline.config.contants import CHUNKING_STRATEGY_METADATA_KEY
from app.features.knowledge.processing.odlh_pipeline.config.contants import DEFAULT_CHUNK_OVERLAP
from app.features.knowledge.processing.odlh_pipeline.config.contants import DEFAULT_CHUNK_SIZE
from app.features.knowledge.processing.odlh_pipeline.config.contants import DEFAULT_ENCODING_NAME
from app.features.knowledge.processing.odlh_pipeline.config.contants import DEFAULT_OPENAI_EMBEDDING_MODEL
from app.features.knowledge.processing.odlh_pipeline.config.contants import EMBEDDING_CONFIG_MISSING_MESSAGE
from app.features.knowledge.processing.odlh_pipeline.config.contants import HEADER_METADATA_PREFIX
from app.features.knowledge.processing.odlh_pipeline.config.contants import IMAGES_METADATA_KEY
from app.features.knowledge.processing.odlh_pipeline.config.contants import JSON_INDENT
from app.features.knowledge.processing.odlh_pipeline.config.contants import TEXT_FILE_ENCODING
from app.features.knowledge.processing.odlh_pipeline.config.contants import TITLE_METADATA_KEY
from app.features.knowledge.processing.odlh_pipeline.core.chunker import chunk_markdown
from app.features.knowledge.processing.odlh_pipeline.core.text_utils import sanitize_title
from app.features.knowledge.processing.odlh_pipeline.models.models import ChunkingStrategy
from app.features.knowledge.processing.odlh_pipeline.models.models import PipelinePaths
from app.features.knowledge.processing.odlh_pipeline.services.chunk_service import _extract_images_from_markdown
from app.features.knowledge.processing.odlh_pipeline.services.chunk_service import _normalize_chunking_strategy
from app.features.knowledge.processing.odlh_pipeline.services.chunk_service import _prepare_output_dirs
from app.features.knowledge.processing.odlh_pipeline.services.chunk_service import _write_manifests
from app.features.knowledge.processing.odlh_pipeline.services.env_service import EnvService


# ==================================================================================================
# 텍스트 청크 산출물 생성 서비스
# --------------------------------------------------------------------------------------------------
# Markdown/TXT 본문을 odlh 방식의 chunks/*.json 산출물로 변환합니다
# ==================================================================================================
class TextChunkExportService:
  # ================================================================================================
  # 초기화
  # ------------------------------------------------------------------------------------------------
  # 텍스트 경로에서 사용할 청킹 설정과 시맨틱 임베딩 설정을 준비합니다
  # ================================================================================================
  def __init__(
    self,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    encoding_name: str = DEFAULT_ENCODING_NAME,
    semantic_embedding_model: str = DEFAULT_OPENAI_EMBEDDING_MODEL,
    api_key: str | None = None,
  ):
    self.chunk_size = chunk_size
    self.chunk_overlap = chunk_overlap
    self.encoding_name = encoding_name
    self.semantic_embedding_model = semantic_embedding_model
    self.api_key = api_key
    self.semantic_embeddings: Embeddings | None = None
    self.env_service = EnvService(api_key=api_key)

  # ================================================================================================
  # 시맨틱 임베딩 준비
  # ------------------------------------------------------------------------------------------------
  # 의미 기반 청킹이 필요한 경우 OpenAI 임베딩 인스턴스를 생성합니다
  # ================================================================================================
  def _build_semantic_embeddings(self) -> Embeddings:
    if self.semantic_embeddings is None:
      self.semantic_embeddings = OpenAIEmbeddings(
        model=self.semantic_embedding_model,
        openai_api_key=self.api_key,
      )
    return self.semantic_embeddings

  # ================================================================================================
  # 텍스트 청크 산출물 생성
  # ------------------------------------------------------------------------------------------------
  # Markdown/TXT 본문을 분석된 전략에 맞춰 Markdown/JSON 산출물로 기록합니다
  # ================================================================================================
  def export(
    self,
    markdown: str,
    paths: PipelinePaths,
    strategy: str | ChunkingStrategy,
  ) -> int:
    normalized_strategy = _normalize_chunking_strategy(strategy)
    semantic_embeddings: Embeddings | None = None
    if normalized_strategy == ChunkingStrategy.SEMANTIC:
      if not self.env_service.has_required_embedding_config():
        raise ValueError(EMBEDDING_CONFIG_MISSING_MESSAGE)
      semantic_embeddings = self._build_semantic_embeddings()

    _prepare_output_dirs(paths)

    markdown_file_name = f"001_{sanitize_title(paths.pdf_path.stem)}.md"
    markdown_file_path = paths.markdown_output_dir / markdown_file_name
    markdown_file_path.write_text(markdown, encoding=TEXT_FILE_ENCODING)

    ai_chunks = chunk_markdown(
      markdown,
      strategy=normalized_strategy,
      chunk_size=self.chunk_size,
      chunk_overlap=self.chunk_overlap,
      encoding_name=self.encoding_name,
      embeddings=semantic_embeddings,
    )
    if not ai_chunks:
      raise ValueError("odlh_pipeline 텍스트 청킹 결과가 비어 있습니다.")

    stem = Path(markdown_file_name).stem
    for idx, ai_chunk in enumerate(ai_chunks, start=1):
      ai_chunk.metadata[CHUNKING_STRATEGY_METADATA_KEY] = normalized_strategy.value

      headers = sorted([key for key in ai_chunk.metadata if key.startswith(HEADER_METADATA_PREFIX)])
      if headers:
        ai_chunk.metadata[TITLE_METADATA_KEY] = ai_chunk.metadata.pop(headers[-1])
        for header_key in headers[:-1]:
          ai_chunk.metadata.pop(header_key, None)

      modified_content, images = _extract_images_from_markdown(ai_chunk.page_content)
      if images:
        ai_chunk.metadata[IMAGES_METADATA_KEY] = images

      json_file_name = f"{stem}_{idx:03d}.json"
      chunk_data = {
        CHUNK_CONTENT_KEY: modified_content,
        CHUNK_METADATA_KEY: ai_chunk.metadata,
      }
      (paths.json_chunk_output_dir / json_file_name).write_text(
        json.dumps(chunk_data, ensure_ascii=False, indent=JSON_INDENT),
        encoding=TEXT_FILE_ENCODING,
      )

    _write_manifests(
      [
        {
          "new_index": 1,
          "filename": markdown_file_name,
          "title": paths.pdf_path.stem,
          "section_code": "1",
          "heading_level": 1,
          "original_index": 1,
          "start_id": 0,
          "end_id": 0,
          "start_pos": 0,
          "end_pos": 0,
          "gap": 0,
        }
      ],
      paths,
    )
    return len(ai_chunks)
