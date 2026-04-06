"""
services 계층에서 공유하는 데이터 모델.
"""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


# ==================================================================================================
# 파이프라인 경로 모델
# --------------------------------------------------------------------------------------------------
# PDF 처리 파이프라인의 입출력 경로를 한 번에 전달하는 데이터 모델
# ==================================================================================================
@dataclass(slots=True, frozen=True)
class PipelinePaths:
  pdf_path: Path
  output_dir: Path
  doc_path: Path
  markdown_path: Path
  markdown_output_dir: Path
  json_chunk_output_dir: Path
  image_output_dir: Path
  raw_image_output_dir: Path


# ==================================================================================================
# heading 윤곽 모델
# --------------------------------------------------------------------------------------------------
# heading 번호 체계 추론 결과를 담는 데이터 모델
# ==================================================================================================
@dataclass(slots=True, frozen=True)
class HeadingOutline:
  code: tuple[int, ...]
  heading_level: int
  section_code: str
  explicit: bool


# ==================================================================================================
# 문서 섹션 범위 모델
# --------------------------------------------------------------------------------------------------
# 문서 내 섹션의 범위와 계층 관계를 표현하는 데이터 모델
# ==================================================================================================
@dataclass(slots=True)
class SectionRange:
  original_index: int
  start_id: int
  end_id: int
  title: str
  heading_level: int
  section_code: str
  explicit: bool = True
  start_pos: int = 0
  end_pos: int = 0
  parent_index: int | None = None

  # ================================================================================================
  # 섹션 길이 계산
  # ================================================================================================
  @property
  def gap(self) -> int:
    return self.end_id - self.start_id


# ==================================================================================================
# 청킹 전략 열거형
# --------------------------------------------------------------------------------------------------
# 지원하는 Markdown 청킹 전략을 정의하는 열거형
# ==================================================================================================
class ChunkingStrategy(StrEnum):
  AUTO = "auto"
  HYBRID = "hybrid"
  SEMANTIC = "semantic"


# ==================================================================================================
# 섹션 통계 모델
# --------------------------------------------------------------------------------------------------
# 개별 Markdown 섹션의 크기 통계를 담는 데이터 모델
# ==================================================================================================
@dataclass(slots=True, frozen=True)
class MarkdownSectionStat:
  heading: str
  heading_level: int
  header_tokens: int
  body_tokens: int


# ==================================================================================================
# Markdown 구조 통계 모델
# --------------------------------------------------------------------------------------------------
# Markdown 전체 구조 분석 결과를 담는 데이터 모델
# ==================================================================================================
@dataclass(slots=True, frozen=True)
class MarkdownStructureMetrics:
  heading_count: int = 0
  header_chunk_count: int = 0
  valid_section_count: int = 0
  empty_header_count: int = 0
  body_token_total: int = 0
  header_token_total: int = 0
  fit_rate: float = 0.0
  oversize_rate: float = 0.0
  undersize_rate: float = 0.0
  empty_header_rate: float = 0.0
  header_to_body_token_ratio: float = 0.0
  median_section_body_tokens: float = 0.0
  p90_section_body_tokens: float = 0.0
  max_section_body_tokens: int = 0
  longest_headerless_run_tokens: int = 0
  largest_sections: tuple[MarkdownSectionStat, ...] = ()


# ==================================================================================================
# 청킹 계획 모델
# --------------------------------------------------------------------------------------------------
# 요청 전략과 최종 선택 전략을 함께 담는 계획 모델
# ==================================================================================================
@dataclass(slots=True, frozen=True)
class ChunkingPlan:
  requested_strategy: ChunkingStrategy
  selected_strategy: ChunkingStrategy
  source_markdown_available: bool
  reasons: tuple[str, ...]
  metrics: MarkdownStructureMetrics
