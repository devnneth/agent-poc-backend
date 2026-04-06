from __future__ import annotations

import re

from app.features.knowledge.common.knowledge_entity import ChunkMetadata
from app.features.knowledge.common.knowledge_entity import DocumentChunk


# ==================================================================================================
# 마크다운 청킹 서비스
# --------------------------------------------------------------------------------------------------
# 마크다운 문서의 헤더 구조를 분석하여 최적의 텍스트 청크를 생성
# ==================================================================================================
class MarkdownChunkingService:
  # ================================================================================================
  # 청킹 서비스 초기화
  # ------------------------------------------------------------------------------------------------
  # 청크 크기 및 중첩 설정 등 파싱 규칙을 초기화
  # ================================================================================================
  def __init__(self, max_chunk_chars: int = 1200):
    self._max_chunk_chars = max_chunk_chars

  # ================================================================================================
  # 문서 청킹 실행
  # ------------------------------------------------------------------------------------------------
  # 전체 문서를 계층 구조에 따라 임베딩 가능한 작은 단위로 분할
  # ================================================================================================
  def chunk(self, markdown: str) -> list[DocumentChunk]:
    sections = self._split_sections(markdown)
    chunks: list[DocumentChunk] = []

    for heading_path, body in sections:
      chunks.extend(self._split_large_section(heading_path, body, len(chunks)))

    if not chunks:
      raise ValueError("청킹할 본문이 없습니다.")

    return chunks

  # ================================================================================================
  # 섹션 분할
  # ------------------------------------------------------------------------------------------------
  # 마크다운 헤더를 기준으로 문서의 각 섹션을 구분하여 추출
  # ================================================================================================
  def _split_sections(self, markdown: str) -> list[tuple[list[str], str]]:
    heading_path: list[str] = []
    buffers: list[tuple[list[str], list[str]]] = []
    current_lines: list[str] = []

    for line in markdown.splitlines():
      heading_match = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
      if heading_match:
        if current_lines:
          buffers.append((heading_path.copy(), current_lines.copy()))
          current_lines.clear()

        level = len(heading_match.group(1))
        title = heading_match.group(2).strip()
        heading_path = heading_path[: level - 1]
        heading_path.append(title)
        continue

      current_lines.append(line)

    if current_lines:
      buffers.append((heading_path.copy(), current_lines.copy()))

    return [(path, "\n".join(lines).strip()) for path, lines in buffers if "\n".join(lines).strip()]

  # ================================================================================================
  # 대형 섹션 세분화
  # ------------------------------------------------------------------------------------------------
  # 제한 크기를 초과하는 섹션을 의미 단위에 맞춰 추가로 분할
  # ================================================================================================
  def _split_large_section(
    self,
    heading_path: list[str],
    body: str,
    chunk_offset: int,
  ) -> list[DocumentChunk]:
    parts = [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip()]
    if not parts:
      return []

    chunks: list[DocumentChunk] = []
    buffer = ""

    for part in parts:
      candidate = f"{buffer}\n\n{part}".strip() if buffer else part
      if buffer and len(candidate) > self._max_chunk_chars:
        chunks.append(self._build_chunk(chunk_offset + len(chunks), buffer, heading_path))
        buffer = part
        continue
      buffer = candidate

    if buffer:
      chunks.append(self._build_chunk(chunk_offset + len(chunks), buffer, heading_path))

    return chunks

  # ================================================================================================
  # 청크 객체 빌드
  # ------------------------------------------------------------------------------------------------
  # 분할된 텍스트와 메타데이터를 결합하여 최종 청크 모델을 생성
  # ================================================================================================
  def _build_chunk(self, chunk_index: int, content: str, heading_path: list[str]) -> DocumentChunk:
    first_line = content.splitlines()[0].strip() if content.splitlines() else content.strip()
    content_type = "paragraph"
    if first_line.startswith(("-", "*", "+")):
      content_type = "list"
    elif "|" in first_line:
      content_type = "table"
    elif heading_path:
      content_type = "section"

    return DocumentChunk(
      chunk_index=chunk_index,
      content=content,
      metadata=ChunkMetadata(
        heading_path=heading_path,
        content_type=content_type,
      ),
    )
