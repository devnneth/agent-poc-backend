"""
Markdown 구조 기반 청킹 유틸리티.
"""

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_experimental.text_splitter import SemanticChunker
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.features.knowledge.processing.odlh_pipeline.config.contants import BREADCRUMB_PREFIX
from app.features.knowledge.processing.odlh_pipeline.config.contants import DEFAULT_CHUNK_OVERLAP
from app.features.knowledge.processing.odlh_pipeline.config.contants import DEFAULT_CHUNK_SIZE
from app.features.knowledge.processing.odlh_pipeline.config.contants import DEFAULT_ENCODING_NAME
from app.features.knowledge.processing.odlh_pipeline.config.contants import DEFAULT_MIN_CHUNK_LENGTH
from app.features.knowledge.processing.odlh_pipeline.config.contants import FENCED_CODE_BLOCK_MARKER
from app.features.knowledge.processing.odlh_pipeline.config.contants import HEADERS_TO_SPLIT_ON
from app.features.knowledge.processing.odlh_pipeline.config.contants import MARKDOWN_HEADING_PATTERN
from app.features.knowledge.processing.odlh_pipeline.config.contants import MAX_HEADING_TEXT_LENGTH
from app.features.knowledge.processing.odlh_pipeline.config.contants import MIN_MERGED_CHUNK_LENGTH
from app.features.knowledge.processing.odlh_pipeline.config.contants import NON_SIGNAL_TEXT_PATTERN
from app.features.knowledge.processing.odlh_pipeline.config.contants import SEMANTIC_SENTENCE_SPLIT_REGEX
from app.features.knowledge.processing.odlh_pipeline.models.models import ChunkingStrategy


# ==================================================================================================
# breadcrumb 안내문 제거
# ==================================================================================================
def _strip_navigation_lines(content: str) -> str:
  return "\n".join(line for line in content.splitlines() if not line.strip().startswith(BREADCRUMB_PREFIX))


# ==================================================================================================
# 의미 길이 계산용 텍스트 추출
# ==================================================================================================
def _signal_text(content: str) -> str:
  # breadcrumb를 제외한 본문만 사용
  stripped_content = _strip_navigation_lines(content)
  return NON_SIGNAL_TEXT_PATTERN.sub("", stripped_content)


# ==================================================================================================
# 본문 내용 존재 여부 확인
# ==================================================================================================
def _has_meaningful_body_content(content: str) -> bool:
  # heading 줄을 제외한 본문 라인만 추출
  body_lines = [line for line in _strip_navigation_lines(content).splitlines() if not MARKDOWN_HEADING_PATTERN.match(line.strip())]

  # 실질적인 본문이 있는지 반환
  return bool("\n".join(body_lines).strip())


# ==================================================================================================
# 과도하게 긴 Markdown heading 완화
# ==================================================================================================
def _demote_overlong_markdown_headings(markdown_text: str) -> str:
  # 코드 블록 상태를 유지하며 라인 정규화
  normalized_lines: list[str] = []
  in_fenced_code_block = False

  for line in markdown_text.splitlines():
    stripped_line = line.strip()
    if stripped_line.startswith(FENCED_CODE_BLOCK_MARKER):
      in_fenced_code_block = not in_fenced_code_block
      normalized_lines.append(line)
      continue

    if in_fenced_code_block:
      normalized_lines.append(line)
      continue

    heading_match = MARKDOWN_HEADING_PATTERN.match(line)
    if heading_match is None:
      normalized_lines.append(line)
      continue

    heading_text = heading_match.group(2).strip()
    if len(heading_text) >= MAX_HEADING_TEXT_LENGTH:
      # 지나치게 긴 heading은 일반 문장으로 강등
      normalized_lines.append(heading_text)
      continue

    normalized_lines.append(line)

  # 정규화된 Markdown 반환
  return "\n".join(normalized_lines)


# ==================================================================================================
# 두 청크 병합
# ==================================================================================================
def _merge_chunk_pair(left: Document, right: Document) -> Document:
  # 좌측 메타데이터를 기준으로 병합 시작
  metadata = dict(left.metadata)
  for key, value in right.metadata.items():
    current_value = metadata.get(key)
    if current_value is None or current_value == value:
      metadata[key] = value
      continue

    if key == "title":
      metadata[key] = f"{current_value} > {value}"
      continue

    metadata[key] = value

  # 본문을 이어 붙여 새 청크 생성
  merged_content = f"{left.page_content.rstrip()}\n\n{right.page_content.lstrip()}"
  return Document(page_content=merged_content, metadata=metadata)


# ==================================================================================================
# 작은 청크 병합
# ==================================================================================================
def _merge_small_chunks(chunks: list[Document], min_merged_chunk_length: int) -> list[Document]:
  # 빈 입력 처리
  if not chunks:
    return []

  # 첫 청크를 기준으로 순차 병합
  merged_chunks: list[Document] = []
  pending_chunk = chunks[0]

  for chunk in chunks[1:]:
    if len(_signal_text(pending_chunk.page_content)) < min_merged_chunk_length:
      pending_chunk = _merge_chunk_pair(pending_chunk, chunk)
      continue

    merged_chunks.append(pending_chunk)
    pending_chunk = chunk

  # 마지막 청크까지 병합 규칙 적용
  if merged_chunks and len(_signal_text(pending_chunk.page_content)) < min_merged_chunk_length:
    merged_chunks[-1] = _merge_chunk_pair(merged_chunks[-1], pending_chunk)
  else:
    merged_chunks.append(pending_chunk)

  return merged_chunks


# ==================================================================================================
# heading 기준 1차 분할
# ==================================================================================================
def _split_markdown_by_headers(markdown_text: str) -> list[Document]:
  # Markdown heading 기준으로 1차 분할
  markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=list(HEADERS_TO_SPLIT_ON), strip_headers=False)
  initial_chunks = markdown_splitter.split_text(markdown_text)

  # 본문이 있는 청크만 유지
  return [chunk for chunk in initial_chunks if chunk.page_content and _has_meaningful_body_content(chunk.page_content)]


# ==================================================================================================
# 의미 단위 청크 분할
# ==================================================================================================
def _semantic_split_documents(
  header_chunks: list[Document],
  chunk_size: int,
  chunk_overlap: int,
  encoding_name: str,
  embeddings: Embeddings,
) -> list[Document]:
  # LangChain SemanticChunker로 의미 경계를 먼저 나눈 뒤 토큰 길이 기준으로 보정
  semantic_chunker = SemanticChunker(
    embeddings=embeddings,
    sentence_split_regex=SEMANTIC_SENTENCE_SPLIT_REGEX,
  )
  semantic_chunks = semantic_chunker.split_documents(header_chunks)
  token_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    encoding_name=encoding_name,
    chunk_size=chunk_size,
    chunk_overlap=chunk_overlap,
  )
  return token_splitter.split_documents(semantic_chunks)


# ==================================================================================================
# 하이브리드 Markdown 청킹
# ==================================================================================================
def chunk_hybrid_markdown(
  markdown_text: str,
  chunk_size: int = DEFAULT_CHUNK_SIZE,
  chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
  encoding_name: str = DEFAULT_ENCODING_NAME,
  min_chunk_length: int = DEFAULT_MIN_CHUNK_LENGTH,
  min_merged_chunk_length: int = MIN_MERGED_CHUNK_LENGTH,
) -> list[Document]:
  # 빈 입력은 즉시 반환
  if not markdown_text or not markdown_text.strip():
    return []

  # Markdown 구조를 정규화한 뒤 heading 기준으로 1차 분할
  markdown_text = _demote_overlong_markdown_headings(markdown_text)
  valid_header_chunks = _split_markdown_by_headers(markdown_text)

  # 토큰 길이 기준으로 2차 분할
  token_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    encoding_name=encoding_name,
    chunk_size=chunk_size,
    chunk_overlap=chunk_overlap,
  )

  # 너무 작은 청크를 병합
  final_chunks = token_splitter.split_documents(valid_header_chunks)
  merged_chunks = _merge_small_chunks(final_chunks, min_merged_chunk_length=min_merged_chunk_length)

  # ------------------------------------------------------------------------------------------------
  # 유효 청크 여부 확인
  # ------------------------------------------------------------------------------------------------
  def is_valid_chunk(content: str) -> bool:
    return len(_signal_text(content)) >= min_chunk_length

  return [chunk for chunk in merged_chunks if is_valid_chunk(chunk.page_content)]


# ==================================================================================================
# 시맨틱 Markdown 청킹
# ==================================================================================================
def chunk_semantic_markdown(
  markdown_text: str,
  chunk_size: int = DEFAULT_CHUNK_SIZE,
  chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
  encoding_name: str = DEFAULT_ENCODING_NAME,
  embeddings: Embeddings | None = None,
  min_chunk_length: int = DEFAULT_MIN_CHUNK_LENGTH,
  min_merged_chunk_length: int = MIN_MERGED_CHUNK_LENGTH,
) -> list[Document]:
  # 빈 입력은 즉시 반환
  if not markdown_text or not markdown_text.strip():
    return []

  # Markdown 구조를 정규화한 뒤 heading 기준으로 1차 분할
  markdown_text = _demote_overlong_markdown_headings(markdown_text)
  valid_header_chunks = _split_markdown_by_headers(markdown_text)
  if not valid_header_chunks:
    return []

  # 최소 청크 길이를 넘는 본문이 없으면 시맨틱 분할을 시도하지 않음
  total_signal_length = sum(len(_signal_text(chunk.page_content)) for chunk in valid_header_chunks)
  if total_signal_length < min_chunk_length:
    return []

  if embeddings is None:
    raise ValueError("Semantic chunking requires embeddings to be provided.")

  # 의미 기반으로 재분할
  final_chunks = _semantic_split_documents(
    valid_header_chunks,
    chunk_size=chunk_size,
    chunk_overlap=chunk_overlap,
    encoding_name=encoding_name,
    embeddings=embeddings,
  )

  # 너무 작은 청크를 병합
  merged_chunks = _merge_small_chunks(final_chunks, min_merged_chunk_length=min_merged_chunk_length)

  # ------------------------------------------------------------------------------------------------
  # 유효 청크 여부 확인
  # ------------------------------------------------------------------------------------------------
  def is_valid_chunk(content: str) -> bool:
    return len(_signal_text(content)) >= min_chunk_length

  return [chunk for chunk in merged_chunks if is_valid_chunk(chunk.page_content)]


# ==================================================================================================
# 전략별 Markdown 청킹 진입점
# ==================================================================================================
def chunk_markdown(
  markdown_text: str,
  strategy: ChunkingStrategy = ChunkingStrategy.HYBRID,
  chunk_size: int = DEFAULT_CHUNK_SIZE,
  chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
  encoding_name: str = DEFAULT_ENCODING_NAME,
  embeddings: Embeddings | None = None,
  min_chunk_length: int = DEFAULT_MIN_CHUNK_LENGTH,
  min_merged_chunk_length: int = MIN_MERGED_CHUNK_LENGTH,
) -> list[Document]:
  # 시맨틱 전략이면 의미 기반 청커 사용
  if strategy == ChunkingStrategy.SEMANTIC:
    return chunk_semantic_markdown(
      markdown_text,
      chunk_size=chunk_size,
      chunk_overlap=chunk_overlap,
      encoding_name=encoding_name,
      embeddings=embeddings,
      min_chunk_length=min_chunk_length,
      min_merged_chunk_length=min_merged_chunk_length,
    )

  # 기본은 하이브리드 청커 사용
  return chunk_hybrid_markdown(
    markdown_text,
    chunk_size=chunk_size,
    chunk_overlap=chunk_overlap,
    encoding_name=encoding_name,
    min_chunk_length=min_chunk_length,
    min_merged_chunk_length=min_merged_chunk_length,
  )
