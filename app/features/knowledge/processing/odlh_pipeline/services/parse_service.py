"""
2/5 단계 : 문서 변환 서비스.

원본 문서를 opendataloader를 사용해 JSON + Markdown 중간 산출물로 변환한다.
"""

from pathlib import Path

from opendataloader_pdf import convert as opendataloader_pdf_convert

from app.features.knowledge.processing.odlh_pipeline.config.contants import DEFAULT_HYBRID_BACKEND_URL
from app.features.knowledge.processing.odlh_pipeline.config.contants import OPENDATALOADER_FORMAT
from app.features.knowledge.processing.odlh_pipeline.config.contants import OPENDATALOADER_HYBRID_ENGINE
from app.features.knowledge.processing.odlh_pipeline.config.contants import OPENDATALOADER_HYBRID_MODE
from app.features.knowledge.processing.odlh_pipeline.config.contants import OPENDATALOADER_QUIET
from app.features.knowledge.processing.odlh_pipeline.config.contants import OPENDATALOADER_SANITIZE
from app.features.knowledge.processing.odlh_pipeline.config.contants import OPENDATALOADER_TABLE_METHOD
from app.features.knowledge.processing.odlh_pipeline.config.contants import OPENDATALOADER_USE_STRUCT_TREE
from app.features.knowledge.processing.odlh_pipeline.core.paths import resolve_pipeline_paths
from app.features.knowledge.processing.odlh_pipeline.models.models import PipelinePaths
from app.features.knowledge.processing.odlh_pipeline.services.cleanup_service import CleanupService


# ==================================================================================================
# 문서 변환 서비스
# --------------------------------------------------------------------------------------------------
# PDF를 중간 JSON과 Markdown 산출물로 변환하는 서비스
# ==================================================================================================
class ParseService:
  # ================================================================================================
  # 초기화
  # ================================================================================================
  def __init__(
    self,
    output_dir: str | Path | None = None,
    backend_url: str = DEFAULT_HYBRID_BACKEND_URL,
  ) -> None:
    # 출력 설정 및 의존 서비스 저장
    self.output_dir = output_dir
    self.backend_url = backend_url
    self.cleanup_service = CleanupService()
    self.last_paths: PipelinePaths | None = None

  # ================================================================================================
  # PDF를 중간 산출물로 변환
  # ================================================================================================
  def convert(self, pdf_path: str | Path) -> PipelinePaths:
    # 출력 경로 계산 및 기존 산출물 정리
    paths = resolve_pipeline_paths(pdf_path, self.output_dir)
    self.cleanup_service.clear_previous_outputs(paths)
    paths.output_dir.mkdir(parents=True, exist_ok=True)

    # opendataloader 변환 실행
    opendataloader_pdf_convert(
      input_path=str(paths.pdf_path),
      output_dir=str(paths.output_dir),
      format=OPENDATALOADER_FORMAT,
      table_method=OPENDATALOADER_TABLE_METHOD,
      sanitize=OPENDATALOADER_SANITIZE,
      hybrid=OPENDATALOADER_HYBRID_ENGINE,
      hybrid_mode=OPENDATALOADER_HYBRID_MODE,
      hybrid_url=self.backend_url,
      use_struct_tree=OPENDATALOADER_USE_STRUCT_TREE,
      quiet=OPENDATALOADER_QUIET,
    )

    # 마지막 결과 경로 저장
    self.last_paths = paths
    return paths

  # ================================================================================================
  # 기존 호환용 PDF -> Markdown 호출
  # ================================================================================================
  def pdf_to_md(self, pdf_path: str | Path) -> bool:
    # 변환 성공 시 True 반환
    self.convert(pdf_path)
    return True
