from __future__ import annotations

import re
from pathlib import Path
from typing import ClassVar

from app.features.knowledge.common.knowledge_entity import ParsedDocument


# ==================================================================================================
# 텍스트 소스 서비스
# --------------------------------------------------------------------------------------------------
# Markdown/TXT 파일을 공통 문서 계약으로 읽고 이미지 참조를 정규화합니다
# ==================================================================================================
class KnowledgeTextSourceService:
  _MARKDOWN_IMAGE_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<path>[^)]+)\)")

  # ================================================================================================
  # 텍스트 소스 읽기
  # ------------------------------------------------------------------------------------------------
  # Markdown 또는 TXT 파일을 읽어 ParsedDocument 형태로 반환합니다
  # ================================================================================================
  @staticmethod
  def read(upload_path: Path) -> ParsedDocument:
    raw_markdown = upload_path.read_text(encoding="utf-8")
    normalized_markdown, image_references = KnowledgeTextSourceService.normalize_markdown_images(raw_markdown)

    return ParsedDocument(
      markdown=normalized_markdown,
      document_json={"image_references": image_references},
    )

  # ================================================================================================
  # Markdown 이미지 정규화
  # ------------------------------------------------------------------------------------------------
  # Markdown 이미지 태그를 텍스트와 이미지 참조 목록으로 분리합니다
  # ================================================================================================
  @staticmethod
  def normalize_markdown_images(markdown: str) -> tuple[str, list[dict[str, str]]]:
    image_references: list[dict[str, str]] = []

    # ----------------------------------------------------------------------------------------------
    # 이미지 태그 치환
    # ----------------------------------------------------------------------------------------------
    def replace_image(match: re.Match[str]) -> str:
      alt_text = match.group("alt").strip() or "이미지"
      image_path = match.group("path").strip()
      image_references.append({"alt_text": alt_text, "path": image_path})
      return f"이미지: {alt_text}"

    normalized_markdown = KnowledgeTextSourceService._MARKDOWN_IMAGE_PATTERN.sub(replace_image, markdown)
    return normalized_markdown, image_references
