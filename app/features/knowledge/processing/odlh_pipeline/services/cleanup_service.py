"""
5/5 단계 : 산출물 정리 서비스.

중간 산출물 삭제, 이미지 디렉토리 정리, 이전 실행 결과 초기화를 담당한다.
"""

import shutil

from app.features.knowledge.processing.odlh_pipeline.config.contants import LEGACY_CHUNK_DIR_SUFFIX
from app.features.knowledge.processing.odlh_pipeline.models.models import PipelinePaths


# ==================================================================================================
# 산출물 정리 서비스
# --------------------------------------------------------------------------------------------------
# 실행 전후 산출물과 이미지 디렉토리를 정리하는 서비스
# ==================================================================================================
class CleanupService:
  # ================================================================================================
  # 이전 실행 산출물 삭제
  # ================================================================================================
  def clear_previous_outputs(self, paths: PipelinePaths) -> None:
    # 제거 대상 디렉토리와 파일 계산
    legacy_chunk_output_dir = paths.output_dir / f"{paths.pdf_path.stem}{LEGACY_CHUNK_DIR_SUFFIX}"
    directories_to_remove = (
      paths.markdown_output_dir,
      paths.json_chunk_output_dir,
      paths.image_output_dir,
      paths.raw_image_output_dir,
      legacy_chunk_output_dir,
    )
    files_to_remove = (paths.doc_path, paths.markdown_path)

    # 디렉토리 제거
    for directory in directories_to_remove:
      if directory.exists():
        shutil.rmtree(directory)

    # 파일 제거
    for artifact in files_to_remove:
      artifact.unlink(missing_ok=True)

  # ================================================================================================
  # 이미지 출력 디렉토리 준비
  # ================================================================================================
  def prepare_image_output_dir(self, paths: PipelinePaths) -> None:
    # 이전 이미지 디렉토리 제거
    if paths.image_output_dir.exists():
      shutil.rmtree(paths.image_output_dir)

    # 원본 이미지 디렉토리를 최종 위치로 이동
    if paths.raw_image_output_dir.exists():
      paths.raw_image_output_dir.rename(paths.image_output_dir)
    else:
      paths.image_output_dir.mkdir(parents=True, exist_ok=True)

  # ================================================================================================
  # 중간 산출물 정리
  # ================================================================================================
  def remove_intermediate_artifacts(self, paths: PipelinePaths) -> None:
    # JSON/Markdown 중간 파일 삭제
    for artifact in (paths.doc_path, paths.markdown_path):
      artifact.unlink(missing_ok=True)
