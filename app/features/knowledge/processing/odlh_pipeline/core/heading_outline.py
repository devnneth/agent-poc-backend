"""
heading 번호 체계와 outline 추론.
"""

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from app.features.knowledge.processing.odlh_pipeline.config.contants import BOOK_HEADING_LEVELS
from app.features.knowledge.processing.odlh_pipeline.config.contants import CHAPTER_PATTERN
from app.features.knowledge.processing.odlh_pipeline.config.contants import NODE_TYPE_HEADING
from app.features.knowledge.processing.odlh_pipeline.config.contants import SECTION_PATTERN
from app.features.knowledge.processing.odlh_pipeline.models.models import HeadingOutline


# ==================================================================================================
# 책 구조용 heading 여부 확인
# ==================================================================================================
def is_book_heading(node: dict[str, Any]) -> bool:
  return node.get("type") == NODE_TYPE_HEADING and node.get("level") in BOOK_HEADING_LEVELS


# ==================================================================================================
# 명시적 heading 번호 파싱
# ==================================================================================================
def parse_explicit_heading_code(title: str) -> tuple[int, ...] | None:
  # "1장" 형식 파싱
  chapter_match = CHAPTER_PATTERN.match(title)
  if chapter_match is not None:
    return (int(chapter_match.group(1)),)

  # "1.2.3" 형식 파싱
  section_match = SECTION_PATTERN.match(title)
  if section_match is None:
    return None

  return tuple(int(part) for part in section_match.group(1).split("."))


# ==================================================================================================
# 표시용 heading 레벨 계산
# ==================================================================================================
def display_heading_level(code: tuple[int, ...]) -> int:
  # 합성 루트(0) 아래 섹션은 실제 표시 레벨로 보정
  if code and code[0] == 0:
    return max(1, len(code) - 1)
  return max(1, len(code))


# ==================================================================================================
# heading 윤곽 추론
# ==================================================================================================
def infer_heading_outlines(titles: Iterable[str]) -> list[HeadingOutline]:
  # 제목별 명시적 번호 추출
  explicit_codes = [parse_explicit_heading_code(title) for title in titles]

  # 이미 사용 중인 자식 번호 예약
  reserved_children: dict[tuple[int, ...], set[int]] = defaultdict(set)
  for explicit_code in explicit_codes:
    if explicit_code is None or len(explicit_code) == 1:
      continue
    reserved_children[explicit_code[:-1]].add(explicit_code[-1])

  # 명시적/합성 번호를 순서대로 할당
  outlines: list[HeadingOutline] = []
  next_synthetic_child: dict[tuple[int, ...], int] = defaultdict(lambda: 1)
  current_explicit_code: tuple[int, ...] | None = None

  for explicit_code in explicit_codes:
    if explicit_code is not None:
      current_explicit_code = explicit_code
      outlines.append(
        HeadingOutline(
          code=explicit_code,
          heading_level=display_heading_level(explicit_code),
          section_code=".".join(map(str, explicit_code)),
          explicit=True,
        )
      )
      continue

    # 직전 명시적 heading 아래에 합성 번호 부여
    parent_code = current_explicit_code or (0,)
    next_child = next_synthetic_child[parent_code]
    while next_child in reserved_children[parent_code]:
      next_child += 1

    synthetic_code = (*parent_code, next_child)
    next_synthetic_child[parent_code] = next_child + 1
    outlines.append(
      HeadingOutline(
        code=synthetic_code,
        heading_level=display_heading_level(synthetic_code),
        section_code=".".join(map(str, synthetic_code)),
        explicit=False,
      )
    )

  # 계산된 outline 목록 반환
  return outlines


# ==================================================================================================
# 문서 노드별 heading 윤곽 매핑
# ==================================================================================================
def infer_doc_heading_outlines(doc: dict[str, Any]) -> dict[int, HeadingOutline]:
  # 문서 상단 heading 노드만 추출
  heading_nodes = [node for node in doc.get("kids", []) if is_book_heading(node)]

  # 제목 흐름에서 outline 추론
  outlines = infer_heading_outlines(node.get("content", "") for node in heading_nodes)

  # node id 기준으로 lookup 맵 구성
  return {node_id: outline for node, outline in zip(heading_nodes, outlines, strict=True) if (node_id := node.get("id")) is not None}
