from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from opendataloader_pdf import convert as opendataloader_pdf_convert

from app.core.config.environment import settings
from app.features.knowledge.common.knowledge_entity import ParsedDocument


# ==================================================================================================
# 지식 파서 어댑터
# --------------------------------------------------------------------------------------------------
# 외부 파싱 도구를 사용하여 PDF 등 문서를 마크다운으로 변환하는 어댑터
# ==================================================================================================
class KnowledgeParserAdapter:
  _MARKDOWN_SUFFIXES = (".md", ".markdown")

  # ================================================================================================
  # 파서 의존성 확인
  # ------------------------------------------------------------------------------------------------
  # Java 런타임 등 파서 실행에 필요한 환경이 준비되었는지 검증
  # ================================================================================================
  def ensure_dependencies(self) -> None:
    if shutil.which("java") is None:
      raise ValueError("Java 런타임이 필요합니다.")

  # ================================================================================================
  # 문서 변환 실행
  # ------------------------------------------------------------------------------------------------
  # 원본 파일을 처리하여 마크다운 및 JSON 형태의 결과물을 생성
  # ================================================================================================
  def convert(self, file_path: Path, output_dir: Path) -> ParsedDocument:
    self.ensure_dependencies()

    # 이전 실행 산출물이 남아 있으면 이번 결과와 섞일 수 있어 소스별 디렉토리를 비웁니다.
    if output_dir.exists():
      shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
      opendataloader_pdf_convert(
        input_path=str(file_path),
        output_dir=str(output_dir),
        format=settings.RAG_PDF_OUTPUT_FORMATS,
        use_struct_tree=True,
        quiet=True,
      )
    except subprocess.CalledProcessError as error:
      error_message = (error.stderr or error.output or error.stdout or "").strip() or "PDF 변환에 실패했습니다."
      raise ValueError(error_message) from error

    markdown_path = self._resolve_output_file(output_dir, file_path.stem, self._MARKDOWN_SUFFIXES)
    json_path = self._resolve_output_file(output_dir, file_path.stem, ".json")

    return ParsedDocument(
      markdown=markdown_path.read_text(encoding="utf-8"),
      document_json=json.loads(json_path.read_text(encoding="utf-8")),
    )

  # ================================================================================================
  # 출력 파일 경로 결정
  # ------------------------------------------------------------------------------------------------
  # 변환 결과물이 저장될 파일의 물리적 경로를 계산
  # ================================================================================================
  def _resolve_output_file(self, output_dir: Path, expected_stem: str, suffix: str | tuple[str, ...]) -> Path:
    suffixes = (suffix,) if isinstance(suffix, str) else suffix
    candidates = sorted(path for path in output_dir.rglob("*") if path.is_file() and path.suffix.lower() in suffixes)
    if not candidates:
      expected_suffixes = ", ".join(suffixes)
      raise ValueError(f"PDF 변환 결과 {expected_suffixes} 파일이 생성되지 않았습니다.")

    stem_matches = [path for path in candidates if path.stem == expected_stem]
    if len(stem_matches) == 1:
      return stem_matches[0]

    if len(candidates) == 1:
      return candidates[0]

    expected_suffixes = ", ".join(suffixes)
    raise ValueError(f"PDF 변환 결과 {expected_suffixes} 파일을 고유하게 식별하지 못했습니다.")
