"""
파이프라인 경로 계산 및 문서 I/O.
"""

import json
from pathlib import Path
from typing import Any

from app.features.knowledge.processing.odlh_pipeline.config.contants import DEFAULT_OUTPUT_DIRNAME
from app.features.knowledge.processing.odlh_pipeline.config.contants import IMAGE_OUTPUT_DIRNAME
from app.features.knowledge.processing.odlh_pipeline.config.contants import JSON_CHUNK_OUTPUT_DIRNAME
from app.features.knowledge.processing.odlh_pipeline.config.contants import MARKDOWN_OUTPUT_DIRNAME
from app.features.knowledge.processing.odlh_pipeline.config.contants import RAW_IMAGE_DIR_SUFFIX
from app.features.knowledge.processing.odlh_pipeline.config.contants import TEXT_FILE_ENCODING
from app.features.knowledge.processing.odlh_pipeline.models.models import PipelinePaths


# ==================================================================================================
# 파이프라인 경로 계산
# ==================================================================================================
def resolve_pipeline_paths(pdf_path: str | Path, output_dir: str | Path | None = None) -> PipelinePaths:
  # 입력 PDF와 출력 루트 경로 정규화
  resolved_pdf_path = Path(pdf_path).expanduser().resolve()
  resolved_output_root = (Path.cwd() / DEFAULT_OUTPUT_DIRNAME) if output_dir is None else Path(output_dir).expanduser().resolve()
  resolved_output_dir = resolved_output_root if resolved_output_root.name == resolved_pdf_path.stem else resolved_output_root / resolved_pdf_path.stem

  # 단계별 산출물 경로 계산
  doc_path = resolved_output_dir / f"{resolved_pdf_path.stem}.json"
  markdown_path = resolved_output_dir / f"{resolved_pdf_path.stem}.md"
  markdown_output_dir = resolved_output_dir / MARKDOWN_OUTPUT_DIRNAME
  json_chunk_output_dir = resolved_output_dir / JSON_CHUNK_OUTPUT_DIRNAME
  image_output_dir = resolved_output_dir / IMAGE_OUTPUT_DIRNAME
  raw_image_output_dir = resolved_output_dir / f"{resolved_pdf_path.stem}{RAW_IMAGE_DIR_SUFFIX}"

  # 경로 모델 반환
  return PipelinePaths(
    pdf_path=resolved_pdf_path,
    output_dir=resolved_output_dir,
    doc_path=doc_path,
    markdown_path=markdown_path,
    markdown_output_dir=markdown_output_dir,
    json_chunk_output_dir=json_chunk_output_dir,
    image_output_dir=image_output_dir,
    raw_image_output_dir=raw_image_output_dir,
  )


# ==================================================================================================
# 문서 JSON 읽기
# ==================================================================================================
def read_doc(doc_path: str | Path) -> dict[str, Any]:
  # JSON 파일을 열어 문서 구조 로드
  with Path(doc_path).expanduser().resolve().open(encoding=TEXT_FILE_ENCODING) as file:
    return json.load(file)
