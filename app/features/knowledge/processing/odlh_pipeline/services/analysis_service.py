"""
3/5 단계 : 문서 분석 서비스.

원본 Markdown의 구조 품질을 분석해 청킹 계획을 계산한다.
"""

import json
from collections.abc import Callable
from pathlib import Path

import tiktoken
from langchain_text_splitters import MarkdownHeaderTextSplitter

from app.features.knowledge.processing.odlh_pipeline.config.contants import CHUNKING_ANALYSIS_REPORT_FILENAME
from app.features.knowledge.processing.odlh_pipeline.config.contants import DEFAULT_ENCODING_NAME
from app.features.knowledge.processing.odlh_pipeline.config.contants import FENCED_CODE_BLOCK_MARKER
from app.features.knowledge.processing.odlh_pipeline.config.contants import HEADER_FIT_LOWER_BOUND_RATIO
from app.features.knowledge.processing.odlh_pipeline.config.contants import HEADER_FIT_UPPER_BOUND_RATIO
from app.features.knowledge.processing.odlh_pipeline.config.contants import HEADER_OVERSIZE_RATIO
from app.features.knowledge.processing.odlh_pipeline.config.contants import HEADER_UNDERSIZE_RATIO
from app.features.knowledge.processing.odlh_pipeline.config.contants import HEADERS_TO_SPLIT_ON
from app.features.knowledge.processing.odlh_pipeline.config.contants import JSON_INDENT
from app.features.knowledge.processing.odlh_pipeline.config.contants import LARGEST_SECTION_LIMIT
from app.features.knowledge.processing.odlh_pipeline.config.contants import MARKDOWN_HEADING_PATTERN
from app.features.knowledge.processing.odlh_pipeline.config.contants import MAX_HEADERLESS_RUN_TO_CHUNK_SIZE_RATIO
from app.features.knowledge.processing.odlh_pipeline.config.contants import MAX_HEADING_TEXT_LENGTH
from app.features.knowledge.processing.odlh_pipeline.config.contants import MAX_OVERSIZE_SECTION_RATE_FOR_HYBRID
from app.features.knowledge.processing.odlh_pipeline.config.contants import MAX_P90_SECTION_TO_CHUNK_SIZE_RATIO
from app.features.knowledge.processing.odlh_pipeline.config.contants import MEDIAN_PERCENTILE
from app.features.knowledge.processing.odlh_pipeline.config.contants import MIN_MARKDOWN_HEADING_COUNT_FOR_HYBRID
from app.features.knowledge.processing.odlh_pipeline.config.contants import MIN_SECTION_FIT_RATE_FOR_HYBRID
from app.features.knowledge.processing.odlh_pipeline.config.contants import NO_HEADING_PLACEHOLDER
from app.features.knowledge.processing.odlh_pipeline.config.contants import P90_PERCENTILE
from app.features.knowledge.processing.odlh_pipeline.config.contants import TEXT_FILE_ENCODING
from app.features.knowledge.processing.odlh_pipeline.models.models import ChunkingPlan
from app.features.knowledge.processing.odlh_pipeline.models.models import ChunkingStrategy
from app.features.knowledge.processing.odlh_pipeline.models.models import MarkdownSectionStat
from app.features.knowledge.processing.odlh_pipeline.models.models import MarkdownStructureMetrics


# ==================================================================================================
# 청킹 전략 정규화
# ==================================================================================================
def normalize_chunking_strategy(value: str | ChunkingStrategy) -> ChunkingStrategy:
  if isinstance(value, ChunkingStrategy):
    return value
  return ChunkingStrategy(value.strip().lower())


# ==================================================================================================
# 과도하게 긴 Markdown heading 완화
# ==================================================================================================
def _demote_overlong_markdown_headings(markdown_text: str) -> str:
  # 코드 블록 상태를 유지하며 라인 단위 정규화
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
      # 지나치게 긴 heading은 일반 본문으로 강등
      normalized_lines.append(heading_text)
      continue

    normalized_lines.append(line)

  # 정규화된 Markdown 반환
  return "\n".join(normalized_lines)


# ==================================================================================================
# Markdown heading 라인 수집
# ==================================================================================================
def _iter_heading_lines(markdown_text: str) -> list[tuple[int, str]]:
  # 코드 블록을 제외하고 heading 정보 추출
  headings: list[tuple[int, str]] = []
  in_fenced_code_block = False

  for line in markdown_text.splitlines():
    stripped_line = line.strip()
    if stripped_line.startswith(FENCED_CODE_BLOCK_MARKER):
      in_fenced_code_block = not in_fenced_code_block
      continue

    if in_fenced_code_block:
      continue

    heading_match = MARKDOWN_HEADING_PATTERN.match(stripped_line)
    if heading_match is None:
      continue

    headings.append((len(heading_match.group(1)), heading_match.group(2).strip()))

  return headings


# ==================================================================================================
# heading 라인 제거
# ==================================================================================================
def _strip_heading_lines(content: str) -> str:
  return "\n".join(line for line in content.splitlines() if not MARKDOWN_HEADING_PATTERN.match(line.strip())).strip()


# ==================================================================================================
# 토큰 수 계산기 생성
# ==================================================================================================
def _token_count_factory(encoding_name: str) -> Callable[[str], int]:
  # 지정 인코더를 사용하는 토큰 카운터 반환
  encoding = tiktoken.get_encoding(encoding_name)
  return lambda text: len(encoding.encode(text))


# ==================================================================================================
# 백분위수 계산
# --------------------------------------------------------------------------------------------------
# 정렬된 값 위에서 percentile 위치를 0 ~ (n - 1) 구간의 실수 좌표로 계산한다.
# 이렇게 하면 0.0은 첫 값, 1.0은 마지막 값에 정확히 대응하고,
# 중간 percentile은 두 인접 인덱스 사이 어딘가에 놓인다.
#
# 예시:
#   values = [10, 20, 40, 80]
#   percentile = 0.25
#   sorted_values = [10, 20, 40, 80]
#   position = 0.25 * (4 - 1) = 0.75
#   lower_index = 0, upper_index = 1, weight = 0.75
#   result = 10 + (20 - 10) * 0.75 = 17.5
#
# 즉, 정렬된 배열의 두 점 사이를 직선으로 잇고 그 중간값을 구하는 선형 보간 방식이다.
# position이 정수면 해당 인덱스 값을 그대로 반환하고,
# 정수가 아니면 lower/upper 사이를 weight 비율만큼 보간한다.
# ==================================================================================================
def _compute_percentile(values: list[int], percentile: float) -> float:
  # 빈 입력과 단일 값 예외 처리
  if not values:
    return 0.0

  sorted_values = sorted(values)
  if len(sorted_values) == 1:
    return float(sorted_values[0])

  # 선형 보간 위치 계산
  position = percentile * (len(sorted_values) - 1)
  lower_index = int(position)
  upper_index = min(lower_index + 1, len(sorted_values) - 1)
  weight = position - lower_index

  # 인접 값 사이를 선형 보간해 반환
  return sorted_values[lower_index] + (sorted_values[upper_index] - sorted_values[lower_index]) * weight


# ==================================================================================================
# 가장 긴 무제목 구간 토큰 수 측정
# ==================================================================================================
def _measure_longest_headerless_run_tokens(markdown_text: str, token_count: Callable[[str], int]) -> int:
  # 현재 누적 구간과 최대 구간 길이 초기화
  in_fenced_code_block = False
  current_lines: list[str] = []
  longest_run_tokens = 0

  # ------------------------------------------------------------------------------------------------
  # 누적 구간 토큰 수 계산
  # ------------------------------------------------------------------------------------------------
  def flush_current_lines() -> int:
    body_text = "\n".join(current_lines).strip()
    return token_count(body_text) if body_text else 0

  # heading을 기준으로 연속 본문 구간 길이 측정
  for line in markdown_text.splitlines():
    stripped_line = line.strip()
    if stripped_line.startswith(FENCED_CODE_BLOCK_MARKER):
      in_fenced_code_block = not in_fenced_code_block
      current_lines.append(line)
      continue

    if not in_fenced_code_block and MARKDOWN_HEADING_PATTERN.match(stripped_line):
      longest_run_tokens = max(longest_run_tokens, flush_current_lines())
      current_lines = []
      continue

    current_lines.append(line)

  # 마지막 구간까지 포함한 최대값 반환
  return max(longest_run_tokens, flush_current_lines())


# ==================================================================================================
# Markdown 구조 분석
# ==================================================================================================
def _analyze_markdown_structure(markdown_text: str, chunk_size: int, encoding_name: str = DEFAULT_ENCODING_NAME) -> MarkdownStructureMetrics:
  # 분석에 사용할 Markdown과 도구 준비
  normalized_markdown = _demote_overlong_markdown_headings(markdown_text)
  token_count = _token_count_factory(encoding_name)
  markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=list(HEADERS_TO_SPLIT_ON), strip_headers=False)
  initial_chunks = markdown_splitter.split_text(normalized_markdown)

  # 기본 집계값 초기화
  section_stats: list[MarkdownSectionStat] = []
  heading_count = len(_iter_heading_lines(normalized_markdown))
  header_chunk_count = 0
  empty_header_count = 0
  body_token_total = 0
  header_token_total = 0

  # heading 기준 청크별 통계 수집
  for chunk in initial_chunks:
    content = chunk.page_content.strip()
    if not content:
      continue

    header_lines = [line.strip() for line in content.splitlines() if MARKDOWN_HEADING_PATTERN.match(line.strip())]
    body_text = _strip_heading_lines(content)
    header_tokens = token_count("\n".join(header_lines)) if header_lines else 0
    body_tokens = token_count(body_text) if body_text else 0
    heading_level = 0
    heading_text = NO_HEADING_PLACEHOLDER

    if header_lines:
      header_chunk_count += 1
      heading_match = MARKDOWN_HEADING_PATTERN.match(header_lines[-1])
      if heading_match is not None:
        heading_level = len(heading_match.group(1))
        heading_text = heading_match.group(2).strip()

    if body_tokens == 0 and header_lines:
      empty_header_count += 1

    if body_tokens == 0:
      continue

    # 본문이 있는 섹션만 분포 집계에 반영
    body_token_total += body_tokens
    header_token_total += header_tokens
    section_stats.append(
      MarkdownSectionStat(
        heading=heading_text,
        heading_level=heading_level,
        header_tokens=header_tokens,
        body_tokens=body_tokens,
      )
    )

  # 분포 기반 파생 지표 계산
  body_token_distribution = [section.body_tokens for section in section_stats]
  fit_lower_bound = chunk_size * HEADER_FIT_LOWER_BOUND_RATIO
  fit_upper_bound = chunk_size * HEADER_FIT_UPPER_BOUND_RATIO
  oversize_bound = chunk_size * HEADER_OVERSIZE_RATIO
  undersize_bound = chunk_size * HEADER_UNDERSIZE_RATIO
  valid_section_count = len(section_stats)
  fit_count = sum(1 for body_tokens in body_token_distribution if fit_lower_bound <= body_tokens <= fit_upper_bound)
  oversize_count = sum(1 for body_tokens in body_token_distribution if body_tokens > oversize_bound)
  undersize_count = sum(1 for body_tokens in body_token_distribution if body_tokens < undersize_bound)
  largest_sections = tuple(sorted(section_stats, key=lambda section: section.body_tokens, reverse=True)[:LARGEST_SECTION_LIMIT])

  # 최종 구조 메트릭 반환
  return MarkdownStructureMetrics(
    heading_count=heading_count,
    header_chunk_count=header_chunk_count,
    valid_section_count=valid_section_count,
    empty_header_count=empty_header_count,
    body_token_total=body_token_total,
    header_token_total=header_token_total,
    fit_rate=(fit_count / valid_section_count) if valid_section_count else 0.0,
    oversize_rate=(oversize_count / valid_section_count) if valid_section_count else 0.0,
    undersize_rate=(undersize_count / valid_section_count) if valid_section_count else 0.0,
    empty_header_rate=(empty_header_count / header_chunk_count) if header_chunk_count else 0.0,
    header_to_body_token_ratio=(header_token_total / body_token_total) if body_token_total else 0.0,
    median_section_body_tokens=_compute_percentile(body_token_distribution, MEDIAN_PERCENTILE),
    p90_section_body_tokens=_compute_percentile(body_token_distribution, P90_PERCENTILE),
    max_section_body_tokens=max(body_token_distribution, default=0),
    longest_headerless_run_tokens=_measure_longest_headerless_run_tokens(normalized_markdown, token_count),
    largest_sections=largest_sections,
  )


# ==================================================================================================
# 자동 전략 선택 사유 계산
# ==================================================================================================
def _build_auto_strategy_reasons(metrics: MarkdownStructureMetrics, chunk_size: int) -> tuple[ChunkingStrategy, tuple[str, ...]]:
  # 하이브리드 전략을 막는 조건을 순서대로 수집
  reasons: list[str] = []

  if metrics.heading_count < MIN_MARKDOWN_HEADING_COUNT_FOR_HYBRID:
    reasons.append(f"heading count {metrics.heading_count} < {MIN_MARKDOWN_HEADING_COUNT_FOR_HYBRID}")

  if metrics.valid_section_count == 0:
    reasons.append("header chunks with body content were not found")

  if metrics.oversize_rate > MAX_OVERSIZE_SECTION_RATE_FOR_HYBRID:
    reasons.append(f"oversize rate {metrics.oversize_rate:.2f} > {MAX_OVERSIZE_SECTION_RATE_FOR_HYBRID:.2f}")

  if metrics.p90_section_body_tokens > chunk_size * MAX_P90_SECTION_TO_CHUNK_SIZE_RATIO:
    reasons.append(f"p90 body tokens {metrics.p90_section_body_tokens:.1f} > {chunk_size * MAX_P90_SECTION_TO_CHUNK_SIZE_RATIO:.1f}")

  if metrics.longest_headerless_run_tokens > chunk_size * MAX_HEADERLESS_RUN_TO_CHUNK_SIZE_RATIO:
    reasons.append(f"longest headerless run {metrics.longest_headerless_run_tokens} > {chunk_size * MAX_HEADERLESS_RUN_TO_CHUNK_SIZE_RATIO:.1f}")

  if metrics.fit_rate < MIN_SECTION_FIT_RATE_FOR_HYBRID and metrics.max_section_body_tokens > chunk_size:
    reasons.append(
      f"fit rate {metrics.fit_rate:.2f} < {MIN_SECTION_FIT_RATE_FOR_HYBRID:.2f} while max section body tokens {metrics.max_section_body_tokens} > {chunk_size}"
    )

  # 제약 조건이 있으면 시맨틱 전략 선택
  if reasons:
    return ChunkingStrategy.SEMANTIC, tuple(reasons)

  # 구조가 충분하면 기본 하이브리드 전략 유지
  return ChunkingStrategy.HYBRID, ("markdown headings look sufficient for the default hybrid splitter",)


# ==================================================================================================
# 메트릭 직렬화
# ==================================================================================================
def _serialize_metrics(metrics: MarkdownStructureMetrics) -> dict[str, object]:
  return {
    "heading_count": metrics.heading_count,
    "header_chunk_count": metrics.header_chunk_count,
    "valid_section_count": metrics.valid_section_count,
    "empty_header_count": metrics.empty_header_count,
    "body_token_total": metrics.body_token_total,
    "header_token_total": metrics.header_token_total,
    "fit_rate": metrics.fit_rate,
    "oversize_rate": metrics.oversize_rate,
    "undersize_rate": metrics.undersize_rate,
    "empty_header_rate": metrics.empty_header_rate,
    "header_to_body_token_ratio": metrics.header_to_body_token_ratio,
    "median_section_body_tokens": metrics.median_section_body_tokens,
    "p90_section_body_tokens": metrics.p90_section_body_tokens,
    "max_section_body_tokens": metrics.max_section_body_tokens,
    "longest_headerless_run_tokens": metrics.longest_headerless_run_tokens,
    "largest_sections": [
      {
        "heading": section.heading,
        "heading_level": section.heading_level,
        "header_tokens": section.header_tokens,
        "body_tokens": section.body_tokens,
      }
      for section in metrics.largest_sections
    ],
  }


# ==================================================================================================
# 청킹 임계값 직렬화
# ==================================================================================================
def _build_chunking_thresholds(chunk_size: int) -> dict[str, float]:
  return {
    "fit_lower_bound_ratio": HEADER_FIT_LOWER_BOUND_RATIO,
    "fit_upper_bound_ratio": HEADER_FIT_UPPER_BOUND_RATIO,
    "oversize_ratio": HEADER_OVERSIZE_RATIO,
    "undersize_ratio": HEADER_UNDERSIZE_RATIO,
    "min_markdown_heading_count_for_hybrid": MIN_MARKDOWN_HEADING_COUNT_FOR_HYBRID,
    "min_section_fit_rate_for_hybrid": MIN_SECTION_FIT_RATE_FOR_HYBRID,
    "max_oversize_section_rate_for_hybrid": MAX_OVERSIZE_SECTION_RATE_FOR_HYBRID,
    "max_p90_section_to_chunk_size_ratio": MAX_P90_SECTION_TO_CHUNK_SIZE_RATIO,
    "max_headerless_run_to_chunk_size_ratio": MAX_HEADERLESS_RUN_TO_CHUNK_SIZE_RATIO,
    "fit_lower_bound_tokens": chunk_size * HEADER_FIT_LOWER_BOUND_RATIO,
    "fit_upper_bound_tokens": chunk_size * HEADER_FIT_UPPER_BOUND_RATIO,
    "oversize_tokens": chunk_size * HEADER_OVERSIZE_RATIO,
    "undersize_tokens": chunk_size * HEADER_UNDERSIZE_RATIO,
    "max_p90_tokens_for_hybrid": chunk_size * MAX_P90_SECTION_TO_CHUNK_SIZE_RATIO,
    "max_headerless_run_tokens_for_hybrid": chunk_size * MAX_HEADERLESS_RUN_TO_CHUNK_SIZE_RATIO,
  }


# ==================================================================================================
# 문서 분석 서비스
# --------------------------------------------------------------------------------------------------
# Markdown 구조를 분석해 적절한 청킹 전략을 결정하는 서비스
# ==================================================================================================
class AnalysisService:
  # ================================================================================================
  # 초기화
  # ================================================================================================
  def __init__(
    self,
    chunk_size: int,
    encoding_name: str = DEFAULT_ENCODING_NAME,
    requested_strategy: str | ChunkingStrategy = ChunkingStrategy.AUTO,
  ) -> None:
    # 분석 설정 저장
    self.chunk_size = chunk_size
    self.encoding_name = encoding_name
    self.requested_strategy = requested_strategy

    # 마지막 분석 결과 초기화
    self.last_plan: ChunkingPlan | None = None
    self.last_report_path: Path | None = None

  # ================================================================================================
  # 청킹 계획 계산
  # ================================================================================================
  def _determine_plan(self, markdown_path: str | Path) -> ChunkingPlan:
    # 요청 전략과 Markdown 경로 정규화
    normalized_strategy = normalize_chunking_strategy(self.requested_strategy)
    resolved_markdown_path = Path(markdown_path).expanduser().resolve()

    # 원본 Markdown이 있으면 구조 메트릭 계산
    if resolved_markdown_path.exists():
      metrics = _analyze_markdown_structure(
        resolved_markdown_path.read_text(encoding=TEXT_FILE_ENCODING),
        chunk_size=self.chunk_size,
        encoding_name=self.encoding_name,
      )
      source_markdown_available = True
    else:
      metrics = MarkdownStructureMetrics()
      source_markdown_available = False

    # 수동 전략이면 그대로 계획 반환
    if normalized_strategy != ChunkingStrategy.AUTO:
      reasons = [f"manual override requested {normalized_strategy.value}"]
      if not source_markdown_available:
        reasons.append("raw opendataloader markdown was not found; metrics are unavailable")

      return ChunkingPlan(
        requested_strategy=normalized_strategy,
        selected_strategy=normalized_strategy,
        source_markdown_available=source_markdown_available,
        reasons=tuple(reasons),
        metrics=metrics,
      )

    # 원본 Markdown이 없으면 기본 하이브리드로 폴백
    if not source_markdown_available:
      return ChunkingPlan(
        requested_strategy=normalized_strategy,
        selected_strategy=ChunkingStrategy.HYBRID,
        source_markdown_available=False,
        reasons=("raw opendataloader markdown was not found; fallback to hybrid",),
        metrics=metrics,
      )

    # 메트릭 기반 자동 전략 선택
    selected_strategy, reasons = _build_auto_strategy_reasons(metrics, chunk_size=self.chunk_size)
    return ChunkingPlan(
      requested_strategy=normalized_strategy,
      selected_strategy=selected_strategy,
      source_markdown_available=True,
      reasons=reasons,
      metrics=metrics,
    )

  # ================================================================================================
  # 청킹 계획 리포트 저장
  # ================================================================================================
  def _write_plan_report(self, output_dir: str | Path, plan: ChunkingPlan) -> Path:
    # 출력 경로 준비
    resolved_output_dir = Path(output_dir).expanduser().resolve()
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    report_path = resolved_output_dir / CHUNKING_ANALYSIS_REPORT_FILENAME

    # 저장할 리포트 데이터 구성
    report = {
      "requested_strategy": plan.requested_strategy.value,
      "selected_strategy": plan.selected_strategy.value,
      "source_markdown_available": plan.source_markdown_available,
      "reasons": list(plan.reasons),
      "thresholds": _build_chunking_thresholds(self.chunk_size),
      "metrics": _serialize_metrics(plan.metrics),
    }

    # JSON 파일로 기록
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=JSON_INDENT), encoding=TEXT_FILE_ENCODING)
    return report_path

  # ================================================================================================
  # Markdown 분석 실행
  # ================================================================================================
  def analyze(self, markdown_path: str | Path, output_dir: str | Path | None = None) -> ChunkingPlan:
    # 계획 계산 및 마지막 결과 저장
    plan = self._determine_plan(markdown_path)
    self.last_plan = plan

    # 요청 시 분석 리포트도 함께 저장
    if output_dir is not None:
      self.last_report_path = self._write_plan_report(output_dir, plan)

    return plan

  # ================================================================================================
  # 구조화 문서 여부 확인
  # ================================================================================================
  def is_structured(self, markdown_path: str | Path) -> bool:
    # 하이브리드 전략이 선택되면 구조화 문서로 간주
    plan = self.analyze(markdown_path)
    return plan.selected_strategy == ChunkingStrategy.HYBRID


# ==================================================================================================
# 청킹 계획 계산 공개 함수
# ==================================================================================================
def determine_chunking_plan(
  markdown_path: str | Path,
  chunk_size: int,
  encoding_name: str = DEFAULT_ENCODING_NAME,
  requested_strategy: str | ChunkingStrategy = ChunkingStrategy.AUTO,
) -> ChunkingPlan:
  # 일회성 분석 서비스 생성
  service = AnalysisService(
    chunk_size=chunk_size,
    encoding_name=encoding_name,
    requested_strategy=requested_strategy,
  )

  # 내부 계획 계산 로직 재사용
  return service._determine_plan(markdown_path)


# ==================================================================================================
# 청킹 계획 리포트 저장 공개 함수
# ==================================================================================================
def write_chunking_plan_report(output_dir: str | Path, chunk_size: int, plan: ChunkingPlan) -> Path:
  # 리포트 저장용 분석 서비스 생성
  service = AnalysisService(
    chunk_size=chunk_size,
    requested_strategy=plan.requested_strategy,
  )

  # 내부 리포트 저장 로직 재사용
  return service._write_plan_report(output_dir, plan)
