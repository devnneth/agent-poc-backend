"""
텍스트 정규화 유틸리티.

순수 문자열 정리와 파일명 안전 변환에만 집중한다.
"""

from app.features.knowledge.processing.odlh_pipeline.config.contants import DEFAULT_UNTITLED_TITLE
from app.features.knowledge.processing.odlh_pipeline.config.contants import LEADING_CHAPTER_NUMBER_PATTERN
from app.features.knowledge.processing.odlh_pipeline.config.contants import LEADING_SECTION_NUMBER_PATTERN
from app.features.knowledge.processing.odlh_pipeline.config.contants import MULTI_BLANK_LINES_PATTERN
from app.features.knowledge.processing.odlh_pipeline.config.contants import SAFE_TITLE_NON_WORD_PATTERN
from app.features.knowledge.processing.odlh_pipeline.config.contants import SAFE_TITLE_UNDERSCORE_PATTERN
from app.features.knowledge.processing.odlh_pipeline.config.contants import WHITESPACE_EXCEPT_NEWLINE_PATTERN


# ==================================================================================================
# 텍스트 정리
# ==================================================================================================
def clean_text(text: str) -> str:
  # 제어 문자와 불필요한 공백 정리
  normalized = text.replace("\x00", "")
  normalized = WHITESPACE_EXCEPT_NEWLINE_PATTERN.sub(" ", normalized)
  normalized = MULTI_BLANK_LINES_PATTERN.sub("\n\n", normalized)

  # 앞뒤 공백 제거
  return normalized.strip()


# ==================================================================================================
# 파일명용 제목 정리
# ==================================================================================================
def sanitize_title(title: str) -> str:
  # 제목을 안전한 식별자 형태로 변환
  safe_title = SAFE_TITLE_NON_WORD_PATTERN.sub("_", clean_text(title))
  safe_title = SAFE_TITLE_UNDERSCORE_PATTERN.sub("_", safe_title).strip("_")

  # 빈 제목은 기본값으로 대체
  return safe_title or DEFAULT_UNTITLED_TITLE


# ==================================================================================================
# 선행 섹션 번호 제거
# ==================================================================================================
def strip_leading_section_number(title: str) -> str:
  # 장/절 번호 접두사 제거
  normalized = LEADING_CHAPTER_NUMBER_PATTERN.sub("", title)
  normalized = LEADING_SECTION_NUMBER_PATTERN.sub("", normalized)

  # 남은 텍스트 정리
  return clean_text(normalized)
