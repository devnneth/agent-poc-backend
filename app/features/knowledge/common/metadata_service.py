import logging
import re
from collections import Counter
from typing import Any

from app.features.knowledge.common.knowledge_entity import ImageReference
from app.features.knowledge.common.knowledge_entity import SourceMetadata
from app.features.llm.llm_service import LLMServiceFactory

_TOKEN_PATTERN = re.compile(r"[가-힣A-Za-z0-9]{2,}")
_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?다요])\s+")
_MARKDOWN_CLEANUP_PATTERN = re.compile(r"[#>*`_\-\[\]\(\)|]")

logger = logging.getLogger(__name__)


# ==================================================================================================
# 지식 메타데이터 서비스
# --------------------------------------------------------------------------------------------------
# 문서 내용을 분석하여 대표 키워드 및 설명을 자동으로 생성하는 서비스
# ==================================================================================================
class KnowledgeMetadataService:
  _KEYWORD_SOURCE_MAX_CHARS = 4000
  _DESCRIPTION_SOURCE_MAX_CHARS = 4000

  # ================================================================================================
  # 메타데이터 구축
  # ------------------------------------------------------------------------------------------------
  # 전체 문서 내용을 요약하고 핵심 키워드를 추출하여 메타데이터를 구성
  # ================================================================================================
  @staticmethod
  def build(markdown: str, document_json: dict[str, Any]) -> SourceMetadata:
    plain_text = KnowledgeMetadataService._to_plain_text(markdown)
    keywords = KnowledgeMetadataService._extract_keywords_with_fallback(plain_text)
    description = KnowledgeMetadataService._build_description(plain_text, keywords)
    image_references = KnowledgeMetadataService._extract_image_references(document_json)

    return SourceMetadata(
      topic_keywords=keywords,
      description=description,
      parser="opendataloader-pdf",
      content_format="markdown",
      page_count=KnowledgeMetadataService._extract_page_count(document_json),
      has_tables=KnowledgeMetadataService._detect_tables(markdown, document_json),
      has_images=KnowledgeMetadataService._detect_images(document_json, image_references),
      image_references=image_references,
    )

  # ================================================================================================
  # 평문 변환
  # ------------------------------------------------------------------------------------------------
  # 분석을 위해 마크다운이나 특수 기호를 제거하고 일반 텍스트로 변환
  # ================================================================================================
  @staticmethod
  def _to_plain_text(markdown: str) -> str:
    cleaned = _MARKDOWN_CLEANUP_PATTERN.sub(" ", markdown)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
      raise ValueError("메타데이터 생성을 위한 본문이 비어 있습니다.")
    return cleaned

  # ================================================================================================
  # 키워드 추출 폴백 처리
  # ------------------------------------------------------------------------------------------------
  # LLM 기반 추출 실패 시 규칙 기반 방식으로 안전하게 전환하여 처리
  # ================================================================================================
  @staticmethod
  def _extract_keywords_with_fallback(plain_text: str) -> list[str]:
    try:
      return KnowledgeMetadataService._extract_keywords_with_llm(plain_text)
    except Exception as exc:
      logger.warning("LLM 기반 토픽 키워드 추출에 실패하여 규칙 기반으로 폴백합니다. error=%s", str(exc))
      return KnowledgeMetadataService._extract_keywords(plain_text)

  # ================================================================================================
  # LLM 기반 키워드 추출
  # ------------------------------------------------------------------------------------------------
  # 대규모 언어 모델을 사용하여 문서의 핵심 주제어들을 추출
  # ================================================================================================
  @staticmethod
  def _extract_keywords_with_llm(plain_text: str) -> list[str]:
    llm_service = LLMServiceFactory.get_service("openai")
    source_text = plain_text[: KnowledgeMetadataService._KEYWORD_SOURCE_MAX_CHARS]
    topic_keywords = llm_service.get_topic_keywords(source_text)
    return KnowledgeMetadataService._normalize_keywords(topic_keywords)

  # ================================================================================================
  # 키워드 추출 실행
  # ------------------------------------------------------------------------------------------------
  # 설정된 전략에 따라 문서에서 의미 있는 키워드들을 선별
  # ================================================================================================
  @staticmethod
  def _extract_keywords(plain_text: str) -> list[str]:
    tokens = [token.lower() for token in _TOKEN_PATTERN.findall(plain_text)]
    counts = Counter(tokens)

    keywords = [token for token, _ in counts.most_common(5)]
    if len(keywords) < 5:
      fallback_tokens = [token for token in tokens if token not in keywords]
      keywords.extend(fallback_tokens[: 5 - len(keywords)])

    # ----------------------------------------------------------------------------------------------
    # 본문이 짧은 경우에는 가능한 키워드만 반환하고 ingestion 자체는 계속 진행합니다.
    # ----------------------------------------------------------------------------------------------
    return KnowledgeMetadataService._normalize_keywords(keywords[:5])

  # ================================================================================================
  # 키워드 정규화
  # ------------------------------------------------------------------------------------------------
  # 추출된 키워드들의 중복을 제거하고 표준 형식으로 정리
  # ================================================================================================
  @staticmethod
  def _normalize_keywords(raw_keywords: list[str]) -> list[str]:
    normalized_keywords: list[str] = []
    seen: set[str] = set()

    for keyword in raw_keywords:
      normalized_keyword = keyword.strip().lower()
      if len(normalized_keyword) < 2 or normalized_keyword in seen:
        continue
      seen.add(normalized_keyword)
      normalized_keywords.append(normalized_keyword)
      if len(normalized_keywords) == 5:
        break

    return normalized_keywords

  # ================================================================================================
  # 요약 설명 생성
  # ------------------------------------------------------------------------------------------------
  # 문서의 내용을 한 줄로 요약하는 설명을 구성
  # ================================================================================================
  @staticmethod
  def _build_description(plain_text: str, keywords: list[str]) -> str:
    try:
      return KnowledgeMetadataService._build_description_with_llm(plain_text)
    except Exception as exc:
      logger.warning("LLM 기반 설명 생성에 실패하여 규칙 기반으로 폴백합니다. error=%s", str(exc))
      return KnowledgeMetadataService._build_description_with_rules(plain_text, keywords)

  # ================================================================================================
  # LLM 기반 요약 생성
  # ------------------------------------------------------------------------------------------------
  # 대규모 언어 모델을 활용하여 문서 전체 맥락을 담은 요약을 생성
  # ================================================================================================
  @staticmethod
  def _build_description_with_llm(plain_text: str) -> str:
    llm_service = LLMServiceFactory.get_service("openai")
    source_text = plain_text[: KnowledgeMetadataService._DESCRIPTION_SOURCE_MAX_CHARS]
    description = llm_service.chunk_summary(source_text).strip()
    if not description:
      raise ValueError("LLM 설명 생성 결과가 비어 있습니다.")
    return description

  # ================================================================================================
  # 규칙 기반 설명 생성
  # ------------------------------------------------------------------------------------------------
  # 정의된 규칙에 따라 문서의 메타데이터 설명을 조합합니다
  # ================================================================================================
  @staticmethod
  def _build_description_with_rules(plain_text: str, keywords: list[str]) -> str:
    sentences = [sentence.strip() for sentence in _SENTENCE_SPLIT_PATTERN.split(plain_text) if sentence.strip()]
    if len(sentences) >= 2:
      return " ".join(sentences[:2])

    snippet = plain_text[:180].strip()
    if keywords:
      summary_keyword_text = ", ".join(keywords[:3])
      return f"이 문서는 {summary_keyword_text}를 중심으로 설명합니다. 주요 내용은 {snippet} 입니다."
    return f"이 문서의 주요 내용은 {snippet} 입니다."

  # ================================================================================================
  # 페이지 수 추출
  # ------------------------------------------------------------------------------------------------
  # 문서 본문에서 전체 페이지 수를 식별하여 추출합니다
  # ================================================================================================
  @staticmethod
  def _extract_page_count(document_json: dict[str, Any]) -> int | None:
    pages = document_json.get("pages")
    if isinstance(pages, list):
      return len(pages)

    page_count = document_json.get("page_count")
    if isinstance(page_count, int):
      return page_count

    return None

  # ================================================================================================
  # 표 탐지
  # ------------------------------------------------------------------------------------------------
  # 본문 내 표 형태의 구조가 포함되어 있는지 확인합니다
  # ================================================================================================
  @staticmethod
  def _detect_tables(markdown: str, document_json: dict[str, Any]) -> bool:
    if "|" in markdown:
      return True

    elements = document_json.get("elements", [])
    if isinstance(elements, list):
      return any(isinstance(item, dict) and str(item.get("type", "")).lower() == "table" for item in elements)
    return False

  # ================================================================================================
  # 이미지 탐지
  # ------------------------------------------------------------------------------------------------
  # 본문 내 이미지 참조나 태그가 포함되어 있는지 확인합니다
  # ================================================================================================
  @staticmethod
  def _detect_images(document_json: dict[str, Any], image_references: list[ImageReference]) -> bool:
    if image_references:
      return True

    elements = document_json.get("elements", [])
    if isinstance(elements, list):
      return any(isinstance(item, dict) and str(item.get("type", "")).lower() in {"image", "figure"} for item in elements)
    return False

  # ================================================================================================
  # 이미지 참조 추출
  # ------------------------------------------------------------------------------------------------
  # 문서 내에 포함된 이미지 파일 경로 정보를 수집합니다
  # ================================================================================================
  @staticmethod
  def _extract_image_references(document_json: dict[str, Any]) -> list[ImageReference]:
    raw_references = document_json.get("image_references", [])
    if not isinstance(raw_references, list):
      return []

    image_references: list[ImageReference] = []
    for item in raw_references:
      if not isinstance(item, dict):
        continue

      path = item.get("path")
      if not isinstance(path, str) or not path.strip():
        continue

      alt_text = item.get("alt_text")
      normalized_alt_text = alt_text.strip() if isinstance(alt_text, str) and alt_text.strip() else "이미지"
      image_references.append(ImageReference(alt_text=normalized_alt_text, path=path.strip()))

    return image_references
