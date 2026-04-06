"""
4/5 단계 : 청킹 서비스.

문서 구조에 따라 섹션을 수집하고 최종 Markdown/JSON 청크 산출물을 생성한다.
"""

import json
import re
import shutil
from pathlib import Path
from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from app.features.knowledge.processing.odlh_pipeline.config.contants import BOOK_START_ID
from app.features.knowledge.processing.odlh_pipeline.config.contants import BREADCRUMB_PREFIX
from app.features.knowledge.processing.odlh_pipeline.config.contants import BREADCRUMB_SEPARATOR
from app.features.knowledge.processing.odlh_pipeline.config.contants import CHUNK_CONTENT_KEY
from app.features.knowledge.processing.odlh_pipeline.config.contants import CHUNK_METADATA_KEY
from app.features.knowledge.processing.odlh_pipeline.config.contants import CHUNKING_STRATEGY_METADATA_KEY
from app.features.knowledge.processing.odlh_pipeline.config.contants import DEFAULT_CHUNK_OVERLAP
from app.features.knowledge.processing.odlh_pipeline.config.contants import DEFAULT_CHUNK_SIZE
from app.features.knowledge.processing.odlh_pipeline.config.contants import DEFAULT_ENCODING_NAME
from app.features.knowledge.processing.odlh_pipeline.config.contants import DEFAULT_MIN_CHUNK_LENGTH
from app.features.knowledge.processing.odlh_pipeline.config.contants import DEFAULT_OPENAI_EMBEDDING_MODEL
from app.features.knowledge.processing.odlh_pipeline.config.contants import EMBEDDING_CONFIG_MISSING_MESSAGE
from app.features.knowledge.processing.odlh_pipeline.config.contants import HEADER_METADATA_PREFIX
from app.features.knowledge.processing.odlh_pipeline.config.contants import IMAGE_PLACEHOLDER_TEMPLATE
from app.features.knowledge.processing.odlh_pipeline.config.contants import IMAGES_METADATA_KEY
from app.features.knowledge.processing.odlh_pipeline.config.contants import JSON_INDENT
from app.features.knowledge.processing.odlh_pipeline.config.contants import MANIFEST_FILENAME
from app.features.knowledge.processing.odlh_pipeline.config.contants import MARKDOWN_IMAGE_PATTERN
from app.features.knowledge.processing.odlh_pipeline.config.contants import MAX_HEADING_TEXT_LENGTH
from app.features.knowledge.processing.odlh_pipeline.config.contants import MIN_SECTION_SIGNAL_LENGTH
from app.features.knowledge.processing.odlh_pipeline.config.contants import NAVIGATION_METADATA_KEY
from app.features.knowledge.processing.odlh_pipeline.config.contants import NON_SIGNAL_TEXT_PATTERN
from app.features.knowledge.processing.odlh_pipeline.config.contants import TEXT_FILE_ENCODING
from app.features.knowledge.processing.odlh_pipeline.config.contants import TITLE_METADATA_KEY
from app.features.knowledge.processing.odlh_pipeline.core.chunker import chunk_markdown
from app.features.knowledge.processing.odlh_pipeline.core.heading_outline import infer_doc_heading_outlines
from app.features.knowledge.processing.odlh_pipeline.core.heading_outline import infer_heading_outlines
from app.features.knowledge.processing.odlh_pipeline.core.heading_outline import is_book_heading
from app.features.knowledge.processing.odlh_pipeline.core.node_renderer import build_chunk_markdown
from app.features.knowledge.processing.odlh_pipeline.core.text_utils import clean_text
from app.features.knowledge.processing.odlh_pipeline.core.text_utils import sanitize_title
from app.features.knowledge.processing.odlh_pipeline.core.text_utils import strip_leading_section_number
from app.features.knowledge.processing.odlh_pipeline.models.models import ChunkingStrategy
from app.features.knowledge.processing.odlh_pipeline.models.models import PipelinePaths
from app.features.knowledge.processing.odlh_pipeline.models.models import SectionRange
from app.features.knowledge.processing.odlh_pipeline.services.env_service import EnvService


# ==================================================================================================
# 청킹 전략 정규화
# ==================================================================================================
def _normalize_chunking_strategy(value: str | ChunkingStrategy) -> ChunkingStrategy:
  if isinstance(value, ChunkingStrategy):
    return value
  return ChunkingStrategy(value.strip().lower())


# ==================================================================================================
# 섹션용 heading 여부 확인
# ==================================================================================================
def _is_section_heading(node: dict[str, Any]) -> bool:
  # 책 구조용 heading이 아니면 제외
  if not is_book_heading(node):
    return False

  # 비어 있거나 지나치게 긴 제목은 제외
  title = clean_text(str(node.get("content", "")))
  return bool(title) and len(title) < MAX_HEADING_TEXT_LENGTH


# ==================================================================================================
# 부모 섹션 코드 계산
# ==================================================================================================
def parent_section_code(section_code: str) -> str | None:
  if "." not in section_code:
    return None
  return section_code.rsplit(".", maxsplit=1)[0]


# ==================================================================================================
# breadcrumb 생성
# ==================================================================================================
def build_breadcrumb(section: SectionRange, sections_by_index: dict[int, SectionRange]) -> str:
  # 현재 섹션에서 루트까지 거슬러 올라가며 제목 수집
  path: list[str] = []
  current: SectionRange | None = section
  while current is not None:
    path.append(clean_text(current.title))
    current = sections_by_index.get(current.parent_index) if current.parent_index is not None else None

  # 루트 -> 현재 순서로 정렬
  path.reverse()
  return BREADCRUMB_SEPARATOR.join(path)


# ==================================================================================================
# 문서 섹션 수집
# ==================================================================================================
def collect_subtitles(doc: dict[str, Any]) -> list[SectionRange]:
  # 섹션 후보 heading과 outline 미리 계산
  sections: list[SectionRange] = []
  current_section: SectionRange | None = None
  section_heading_nodes = [node for node in doc.get("kids", []) if _is_section_heading(node)]
  outlines = infer_heading_outlines(node.get("content", "") for node in section_heading_nodes)
  heading_outlines = {node_id: outline for node, outline in zip(section_heading_nodes, outlines, strict=True) if (node_id := node.get("id")) is not None}

  # 문서 노드를 순회하며 섹션 범위 구성
  for node_position, node in enumerate(doc.get("kids", [])):
    node_id = node.get("id")
    if node_id is None or node_id < BOOK_START_ID:
      continue

    if _is_section_heading(node):
      outline = heading_outlines.get(node_id)
      if outline is None:
        continue
      current_section = SectionRange(
        original_index=len(sections) + 1,
        start_id=node_id,
        end_id=node_id,
        title=node.get("content", ""),
        heading_level=outline.heading_level,
        section_code=outline.section_code,
        explicit=outline.explicit,
        start_pos=node_position,
        end_pos=node_position,
      )
      sections.append(current_section)

    if current_section is not None:
      current_section.end_id = max(current_section.end_id, node_id)
      current_section.end_pos = node_position

  # 섹션 코드 기준 부모 관계 연결
  section_index_by_code = {section.section_code: section.original_index for section in sections}
  for section in sections:
    p_code = parent_section_code(section.section_code)
    if p_code is not None:
      section.parent_index = section_index_by_code.get(p_code)

  return sections


# ==================================================================================================
# 섹션 Markdown 파일명 생성
# ==================================================================================================
def chunk_filename(section: SectionRange) -> str:
  # 표시용 제목을 파일명 안전 문자열로 변환
  display_title = strip_leading_section_number(section.title)
  safe_title = sanitize_title(display_title)

  # 명시적 번호가 있으면 섹션 코드 기준으로 파일명 구성
  if section.explicit:
    return f"{section.section_code}_{safe_title}.md"
  return f"{section.original_index:03d}_{safe_title}.md"


# ==================================================================================================
# Markdown 내 이미지 링크 추출
# ==================================================================================================
def _extract_images_from_markdown(content: str) -> tuple[str, list[str]]:
  # 이미지 링크를 placeholder로 바꾸며 경로 목록 수집
  images: list[str] = []

  # ------------------------------------------------------------------------------------------------
  # 이미지 링크 치환
  # ------------------------------------------------------------------------------------------------
  def replace_image(match: re.Match[str]) -> str:
    img_index = len(images)
    images.append(match.group(2))
    return IMAGE_PLACEHOLDER_TEMPLATE.format(index=img_index + 1)

  modified_content = MARKDOWN_IMAGE_PATTERN.sub(replace_image, content)
  return modified_content, images


# ==================================================================================================
# breadcrumb 안내문 제거
# ==================================================================================================
def _strip_navigation_lines(content: str) -> str:
  return "\n".join(line for line in content.splitlines() if not line.strip().startswith(BREADCRUMB_PREFIX))


# ==================================================================================================
# 섹션 의미 길이 계산
# ==================================================================================================
def _signal_text_length(content: str) -> int:
  # breadcrumb를 제외한 본문 기준으로 길이 계산
  stripped_content = _strip_navigation_lines(content)
  return len(NON_SIGNAL_TEXT_PATTERN.sub("", stripped_content))


# ==================================================================================================
# 섹션 복사
# ==================================================================================================
def _copy_section(section: SectionRange) -> SectionRange:
  return SectionRange(
    original_index=section.original_index,
    start_id=section.start_id,
    end_id=section.end_id,
    title=section.title,
    heading_level=section.heading_level,
    section_code=section.section_code,
    explicit=section.explicit,
    start_pos=section.start_pos,
    end_pos=section.end_pos,
    parent_index=section.parent_index,
  )


# ==================================================================================================
# 두 섹션 병합
# ==================================================================================================
def _merge_section_pair(left: SectionRange, right: SectionRange) -> SectionRange:
  return SectionRange(
    original_index=left.original_index,
    start_id=left.start_id,
    end_id=max(left.end_id, right.end_id),
    title=left.title,
    heading_level=left.heading_level,
    section_code=left.section_code,
    explicit=left.explicit,
    start_pos=left.start_pos,
    end_pos=right.end_pos,
    parent_index=left.parent_index,
  )


# ==================================================================================================
# 출력 디렉토리 준비
# ==================================================================================================
def _prepare_output_dirs(paths: PipelinePaths) -> None:
  # 기존 출력 디렉토리를 지우고 새로 생성
  for directory in (paths.markdown_output_dir, paths.json_chunk_output_dir):
    if directory.exists():
      shutil.rmtree(directory)
    directory.mkdir(parents=True, exist_ok=True)


# ==================================================================================================
# 섹션 Markdown 렌더링
# ==================================================================================================
def _render_section_markdown(
  doc: dict[str, Any],
  section: SectionRange,
  heading_outlines: dict[int, Any],
  paths: PipelinePaths,
  breadcrumb: str = "",
) -> str:
  # 지정 섹션 범위를 Markdown으로 렌더링
  return build_chunk_markdown(
    doc,
    section.start_pos,
    section.end_pos,
    paths.markdown_output_dir,
    paths.image_output_dir,
    heading_outlines,
    breadcrumb,
  )


# ==================================================================================================
# 작은 섹션 병합
# ==================================================================================================
def _merge_small_sections(
  doc: dict[str, Any],
  sections: list[SectionRange],
  sections_by_index: dict[int, SectionRange],
  heading_outlines: dict[int, Any],
  paths: PipelinePaths,
  min_section_signal_length: int = MIN_SECTION_SIGNAL_LENGTH,
) -> list[SectionRange]:
  # 빈 입력 처리
  if not sections:
    return []

  # 각 섹션의 실질 본문 길이 측정
  section_signal_lengths: list[tuple[SectionRange, int]] = []
  for section in sections:
    breadcrumb = build_breadcrumb(section, sections_by_index)
    markdown = _render_section_markdown(doc, section, heading_outlines, paths, breadcrumb)
    section_signal_lengths.append((section, _signal_text_length(markdown)))

  # 짧은 섹션을 다음 섹션과 순차 병합
  merged_sections: list[SectionRange] = []
  pending_section = _copy_section(section_signal_lengths[0][0])
  pending_signal_length = section_signal_lengths[0][1]

  for section, signal_length in section_signal_lengths[1:]:
    if pending_signal_length < min_section_signal_length:
      pending_section = _merge_section_pair(pending_section, section)
      pending_signal_length += signal_length
      continue

    merged_sections.append(pending_section)
    pending_section = _copy_section(section)
    pending_signal_length = signal_length

  # 마지막 섹션까지 병합 규칙 적용
  if merged_sections and pending_signal_length < min_section_signal_length:
    merged_sections[-1] = _merge_section_pair(merged_sections[-1], pending_section)
  else:
    merged_sections.append(pending_section)

  return merged_sections


# ==================================================================================================
# 시맨틱 청킹 대상 존재 여부 확인
# ==================================================================================================
def _has_semantic_chunking_targets(
  doc: dict[str, Any],
  all_sections: list[SectionRange],
  valid_sections: list[SectionRange],
  paths: PipelinePaths,
  min_chunk_length: int = DEFAULT_MIN_CHUNK_LENGTH,
) -> bool:
  if not valid_sections:
    return False

  heading_outlines = infer_doc_heading_outlines(doc)
  sections_by_index = {section.original_index: section for section in all_sections}
  merged_sections = _merge_small_sections(doc, valid_sections, sections_by_index, heading_outlines, paths)

  for section in merged_sections:
    breadcrumb = build_breadcrumb(section, sections_by_index)
    section_markdown = _render_section_markdown(doc, section, heading_outlines, paths, breadcrumb)
    if _signal_text_length(section_markdown) >= min_chunk_length:
      return True

  return False


# ==================================================================================================
# 섹션별 Markdown/JSON 청크 쓰기
# ==================================================================================================
def _write_section_chunks(
  doc: dict[str, Any],
  section: SectionRange,
  sections_by_index: dict[int, SectionRange],
  heading_outlines: dict[int, Any],
  paths: PipelinePaths,
  chunking_strategy: ChunkingStrategy,
  chunk_size: int,
  chunk_overlap: int,
  encoding_name: str,
  semantic_embeddings: Embeddings | None,
) -> None:
  # 파일명과 breadcrumb 계산
  file_name = chunk_filename(section)
  breadcrumb = build_breadcrumb(section, sections_by_index)

  # 섹션 Markdown 파일 저장
  section_markdown = _render_section_markdown(doc, section, heading_outlines, paths, breadcrumb)
  (paths.markdown_output_dir / file_name).write_text(section_markdown, encoding=TEXT_FILE_ENCODING)

  # AI 청크 생성
  ai_chunks = chunk_markdown(
    section_markdown,
    strategy=chunking_strategy,
    chunk_size=chunk_size,
    chunk_overlap=chunk_overlap,
    encoding_name=encoding_name,
    embeddings=semantic_embeddings,
  )
  if not ai_chunks:
    return

  # 청크별 메타데이터 보강 및 JSON 저장
  stem = Path(file_name).stem
  for idx, ai_chunk in enumerate(ai_chunks, start=1):
    ai_chunk.metadata[CHUNKING_STRATEGY_METADATA_KEY] = chunking_strategy.value
    if breadcrumb:
      ai_chunk.metadata[NAVIGATION_METADATA_KEY] = breadcrumb

    headers = sorted([k for k in ai_chunk.metadata if k.startswith(HEADER_METADATA_PREFIX)])
    if headers:
      ai_chunk.metadata[TITLE_METADATA_KEY] = ai_chunk.metadata.pop(headers[-1])
      for h in headers[:-1]:
        ai_chunk.metadata.pop(h, None)

    modified_content, images = _extract_images_from_markdown(ai_chunk.page_content)
    if images:
      ai_chunk.metadata[IMAGES_METADATA_KEY] = images

    json_file_name = f"{stem}_{idx:03d}.json"
    chunk_data = {CHUNK_CONTENT_KEY: modified_content, CHUNK_METADATA_KEY: ai_chunk.metadata}
    (paths.json_chunk_output_dir / json_file_name).write_text(
      json.dumps(chunk_data, ensure_ascii=False, indent=JSON_INDENT),
      encoding=TEXT_FILE_ENCODING,
    )


# ==================================================================================================
# manifest 항목 생성
# ==================================================================================================
def _build_manifest_entry(section: SectionRange, new_index: int) -> dict[str, Any]:
  return {
    "new_index": new_index,
    "filename": chunk_filename(section),
    "title": section.title,
    "section_code": section.section_code,
    "heading_level": section.heading_level,
    "original_index": section.original_index,
    "start_id": section.start_id,
    "end_id": section.end_id,
    "start_pos": section.start_pos,
    "end_pos": section.end_pos,
    "gap": section.gap,
  }


# ==================================================================================================
# manifest 파일 저장
# ==================================================================================================
def _write_manifests(manifest: list[dict[str, Any]], paths: PipelinePaths) -> None:
  # Markdown/JSON 출력 디렉토리에 동일한 manifest 기록
  manifest_json = json.dumps(manifest, ensure_ascii=False, indent=JSON_INDENT)
  (paths.markdown_output_dir / MANIFEST_FILENAME).write_text(manifest_json, encoding=TEXT_FILE_ENCODING)
  (paths.json_chunk_output_dir / MANIFEST_FILENAME).write_text(manifest_json, encoding=TEXT_FILE_ENCODING)


# ==================================================================================================
# 청킹 서비스
# --------------------------------------------------------------------------------------------------
# 섹션 수집부터 Markdown과 JSON 청크 생성까지 담당하는 서비스
# ==================================================================================================
class ChunkService:
  # ================================================================================================
  # 초기화
  # ================================================================================================
  def __init__(
    self,
    chunk_size: int,
    chunk_overlap: int,
    encoding_name: str = DEFAULT_ENCODING_NAME,
    semantic_embedding_model: str = DEFAULT_OPENAI_EMBEDDING_MODEL,
    api_key: str | None = None,
  ) -> None:
    # 청킹 설정 저장
    self.chunk_size = chunk_size
    self.chunk_overlap = chunk_overlap
    self.encoding_name = encoding_name
    self.semantic_embedding_model = semantic_embedding_model
    self.api_key = api_key
    self.semantic_embeddings: Embeddings | None = None
    self.env_service = EnvService(api_key=api_key)

    # 마지막 실행 상태 초기화
    self.last_sections: list[SectionRange] = []
    self.last_valid_sections: list[SectionRange] = []
    self.last_chunk_count = 0
    self.last_strategy: ChunkingStrategy | None = None

  # ================================================================================================
  # 시맨틱 임베딩 생성
  # ================================================================================================
  def _build_semantic_embeddings(self) -> Embeddings:
    if self.semantic_embeddings is None:
      self.semantic_embeddings = OpenAIEmbeddings(
        model=self.semantic_embedding_model,
        openai_api_key=self.api_key,
      )
    return self.semantic_embeddings

  # ================================================================================================
  # 문서 청킹 실행
  # ================================================================================================
  def chunk(self, doc: dict[str, Any], paths: PipelinePaths, strategy: str | ChunkingStrategy) -> int:
    # 전략과 섹션 목록 계산
    normalized_strategy = _normalize_chunking_strategy(strategy)
    sections = collect_subtitles(doc)
    valid_sections = [section for section in sections if section.gap > 0]
    semantic_embeddings: Embeddings | None = None

    # 의미 기반 청킹을 실제로 수행할 섹션이 있을 때만 임베딩 설정을 확인
    if normalized_strategy == ChunkingStrategy.SEMANTIC and _has_semantic_chunking_targets(doc, sections, valid_sections, paths):
      if not self.env_service.has_required_embedding_config():
        raise ValueError(EMBEDDING_CONFIG_MISSING_MESSAGE)
      semantic_embeddings = self._build_semantic_embeddings()

    # 최종 Markdown/JSON 청크 작성
    chunk_count = write_chunks(
      doc,
      sections,
      valid_sections,
      paths,
      chunking_strategy=normalized_strategy,
      chunk_size=self.chunk_size,
      chunk_overlap=self.chunk_overlap,
      encoding_name=self.encoding_name,
      semantic_embeddings=semantic_embeddings,
    )

    # 마지막 실행 결과 저장
    self.last_sections = sections
    self.last_valid_sections = valid_sections
    self.last_chunk_count = chunk_count
    self.last_strategy = normalized_strategy
    return chunk_count


# ==================================================================================================
# 최종 청크 쓰기 공개 함수
# ==================================================================================================
def write_chunks(
  doc: dict[str, Any],
  all_sections: list[SectionRange],
  valid_sections: list[SectionRange],
  paths: PipelinePaths,
  chunking_strategy: ChunkingStrategy = ChunkingStrategy.HYBRID,
  chunk_size: int = DEFAULT_CHUNK_SIZE,
  chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
  encoding_name: str = DEFAULT_ENCODING_NAME,
  semantic_embeddings: Embeddings | None = None,
) -> int:
  # 출력 디렉토리와 공통 lookup 준비
  _prepare_output_dirs(paths)
  heading_outlines = infer_doc_heading_outlines(doc)
  sections_by_index = {section.original_index: section for section in all_sections}
  merged_sections = _merge_small_sections(doc, valid_sections, sections_by_index, heading_outlines, paths)

  # 섹션별 산출물 생성 및 manifest 구성
  manifest: list[dict[str, Any]] = []
  for new_index, section in enumerate(merged_sections, start=1):
    _write_section_chunks(
      doc,
      section,
      sections_by_index,
      heading_outlines,
      paths,
      chunking_strategy=chunking_strategy,
      chunk_size=chunk_size,
      chunk_overlap=chunk_overlap,
      encoding_name=encoding_name,
      semantic_embeddings=semantic_embeddings,
    )
    manifest.append(_build_manifest_entry(section, new_index))

  # manifest 저장 후 생성된 섹션 수 반환
  _write_manifests(manifest, paths)
  return len(merged_sections)
