"""
JSON 노드 -> Markdown 렌더링.
"""

import os
from pathlib import Path
from typing import Any

from app.features.knowledge.processing.odlh_pipeline.config.contants import BREADCRUMB_PREFIX
from app.features.knowledge.processing.odlh_pipeline.config.contants import DEFAULT_RENDER_HEADING_LEVEL
from app.features.knowledge.processing.odlh_pipeline.config.contants import LIST_INDENT_UNIT
from app.features.knowledge.processing.odlh_pipeline.config.contants import MAX_HEADING_TEXT_LENGTH
from app.features.knowledge.processing.odlh_pipeline.config.contants import MAX_MARKDOWN_HEADING_LEVEL
from app.features.knowledge.processing.odlh_pipeline.config.contants import MIN_MARKDOWN_HEADING_LEVEL
from app.features.knowledge.processing.odlh_pipeline.config.contants import NODE_TYPE_CAPTION
from app.features.knowledge.processing.odlh_pipeline.config.contants import NODE_TYPE_FOOTER
from app.features.knowledge.processing.odlh_pipeline.config.contants import NODE_TYPE_HEADING
from app.features.knowledge.processing.odlh_pipeline.config.contants import NODE_TYPE_IMAGE
from app.features.knowledge.processing.odlh_pipeline.config.contants import NODE_TYPE_LIST
from app.features.knowledge.processing.odlh_pipeline.config.contants import NODE_TYPE_LIST_ITEM
from app.features.knowledge.processing.odlh_pipeline.config.contants import NODE_TYPE_PARAGRAPH
from app.features.knowledge.processing.odlh_pipeline.core.text_utils import clean_text
from app.features.knowledge.processing.odlh_pipeline.models.models import HeadingOutline


# ==================================================================================================
# 렌더 가능한 heading 여부 확인
# ==================================================================================================
def is_renderable_heading(content: str) -> bool:
  return bool(content) and len(content) < MAX_HEADING_TEXT_LENGTH


# ==================================================================================================
# Markdown heading 레벨 보정
# ==================================================================================================
def markdown_heading_level(heading_level: int) -> int:
  return max(MIN_MARKDOWN_HEADING_LEVEL, min(heading_level, MAX_MARKDOWN_HEADING_LEVEL))


# ==================================================================================================
# 노드 목록 렌더링
# ==================================================================================================
def render_nodes(
  nodes: list[dict[str, Any]],
  chunk_dir: Path,
  image_output_dir: Path,
  heading_outlines: dict[int, HeadingOutline],
  indent: int = 0,
) -> list[str]:
  # 각 노드를 순서대로 Markdown 블록으로 변환
  blocks: list[str] = []
  for node in nodes:
    blocks.extend(render_node(node, chunk_dir, image_output_dir, heading_outlines, indent))
  return blocks


# ==================================================================================================
# 단일 노드 렌더링
# ==================================================================================================
def render_node(
  node: dict[str, Any],
  chunk_dir: Path,
  image_output_dir: Path,
  heading_outlines: dict[int, HeadingOutline],
  indent: int = 0,
) -> list[str]:
  # 공통 속성 정리
  node_type = node.get("type")
  content = clean_text(node.get("content", ""))

  # footer는 출력 제외
  if node_type == NODE_TYPE_FOOTER:
    return []

  # 노드 타입별 Markdown 변환
  blocks: list[str] = []
  if node_type == NODE_TYPE_HEADING:
    if not content:
      blocks.extend(render_nodes(node.get("kids", []), chunk_dir, image_output_dir, heading_outlines, indent))
    elif not is_renderable_heading(content):
      blocks.append(content)
      blocks.extend(render_nodes(node.get("kids", []), chunk_dir, image_output_dir, heading_outlines, indent))
    else:
      node_id = node.get("id")
      outline = heading_outlines.get(node_id) if isinstance(node_id, int) else None
      heading_level = markdown_heading_level(outline.heading_level if outline is not None else DEFAULT_RENDER_HEADING_LEVEL)
      blocks.append(f"{'#' * heading_level} {content}")
  elif node_type == NODE_TYPE_PARAGRAPH:
    if content:
      blocks.append(content)
    blocks.extend(render_nodes(node.get("kids", []), chunk_dir, image_output_dir, heading_outlines, indent))
  elif node_type == NODE_TYPE_CAPTION:
    if content:
      blocks.append(f"*{content}*")
  elif node_type == NODE_TYPE_IMAGE:
    source = node.get("source")
    if source:
      image_path = image_output_dir / Path(str(source)).name
      relative_path = Path(os.path.relpath(image_path, chunk_dir))
      blocks.append(f"![]({relative_path.as_posix()})")
  elif node_type == NODE_TYPE_LIST:
    list_items = node.get("list items", [])
    blocks.extend(render_nodes(list_items, chunk_dir, image_output_dir, heading_outlines, indent))
  elif node_type == NODE_TYPE_LIST_ITEM:
    if content:
      blocks.append(f"{LIST_INDENT_UNIT * indent}- {content}")
    blocks.extend(render_nodes(node.get("kids", []), chunk_dir, image_output_dir, heading_outlines, indent + 1))
  else:
    if content:
      blocks.append(content)
    blocks.extend(render_nodes(node.get("kids", []), chunk_dir, image_output_dir, heading_outlines, indent))

  # 렌더된 블록 반환
  return blocks


# ==================================================================================================
# 섹션 Markdown 조립
# ==================================================================================================
def build_chunk_markdown(
  doc: dict[str, Any],
  start_pos: int,
  end_pos: int,
  chunk_dir: Path,
  image_output_dir: Path,
  heading_outlines: dict[int, HeadingOutline],
  breadcrumb: str | None = None,
) -> str:
  # 선택 구간 노드 렌더링
  selected_nodes = doc.get("kids", [])[start_pos : end_pos + 1]
  blocks = render_nodes(selected_nodes, chunk_dir, image_output_dir, heading_outlines)
  body = "\n\n".join(block for block in blocks if block).strip()
  if not body:
    return ""

  # breadcrumb가 있으면 상단 안내문 추가
  if breadcrumb:
    return f"{BREADCRUMB_PREFIX} {breadcrumb}\n\n{body}\n"
  return body + "\n"
