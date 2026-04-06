from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.features.knowledge.common.knowledge_entity import DocumentChunk
from app.features.knowledge.processing.odlh_pipeline.config.contants import CHUNK_CONTENT_KEY
from app.features.knowledge.processing.odlh_pipeline.config.contants import CHUNK_METADATA_KEY
from app.features.knowledge.processing.odlh_pipeline.config.contants import MANIFEST_FILENAME
from app.features.knowledge.processing.odlh_pipeline.config.contants import TEXT_FILE_ENCODING


# ==================================================================================================
# 청크 파일 로더 서비스
# --------------------------------------------------------------------------------------------------
# odlh_pipeline이 생성한 chunks 디렉토리의 JSON 파일을 공통 DocumentChunk 목록으로 읽어옵니다
# ==================================================================================================
class ChunkFileLoaderService:
  # ================================================================================================
  # 청크 파일 읽기
  # ------------------------------------------------------------------------------------------------
  # chunks 디렉토리의 JSON 파일을 파일명 순서대로 읽어 DocumentChunk 목록으로 변환합니다
  # ================================================================================================
  def load(self, chunk_dir: str | Path) -> list[DocumentChunk]:
    resolved_chunk_dir = Path(chunk_dir).expanduser().resolve()
    chunk_paths = sorted(path for path in resolved_chunk_dir.glob("*.json") if path.name != MANIFEST_FILENAME)
    if not chunk_paths:
      raise ValueError(f"odlh_pipeline 청크 파일을 찾을 수 없습니다: {resolved_chunk_dir}")

    chunks: list[DocumentChunk] = []
    for chunk_index, chunk_path in enumerate(chunk_paths):
      chunk_payload = self._read_chunk_file(chunk_path)
      content = chunk_payload.get(CHUNK_CONTENT_KEY)
      if not isinstance(content, str) or not content.strip():
        raise ValueError(f"청크 파일 content가 비어 있거나 문자열이 아닙니다: {chunk_path}")

      metadata = chunk_payload.get(CHUNK_METADATA_KEY, {})
      if not isinstance(metadata, dict):
        raise ValueError(f"청크 파일 metadata는 dict여야 합니다: {chunk_path}")

      chunks.append(
        DocumentChunk(
          chunk_index=chunk_index,
          content=content,
          metadata=metadata,
        )
      )

    return chunks

  # ================================================================================================
  # 단일 청크 파일 읽기
  # ------------------------------------------------------------------------------------------------
  # JSON 파일을 열어 dict 형태의 청크 페이로드를 반환합니다
  # ================================================================================================
  def _read_chunk_file(self, chunk_path: Path) -> dict[str, Any]:
    raw_payload = json.loads(chunk_path.read_text(encoding=TEXT_FILE_ENCODING))
    if not isinstance(raw_payload, dict):
      raise ValueError(f"청크 파일 최상위 구조는 dict여야 합니다: {chunk_path}")
    return raw_payload
