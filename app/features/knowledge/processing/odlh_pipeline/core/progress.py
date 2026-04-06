"""
JSON 기반 진행률 추적기.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

from app.features.knowledge.processing.odlh_pipeline.config.contants import JSON_INDENT
from app.features.knowledge.processing.odlh_pipeline.config.contants import PROGRESS_STATUS_FAILED
from app.features.knowledge.processing.odlh_pipeline.config.contants import PROGRESS_STATUS_SUCCESS
from app.features.knowledge.processing.odlh_pipeline.config.contants import TEXT_FILE_ENCODING

logger = logging.getLogger(__name__)


# ==================================================================================================
# JSON 진행률 추적기
# --------------------------------------------------------------------------------------------------
# 진행률 로그를 JSON 파일에 누적 기록하는 추적기
# ==================================================================================================
class JsonProgressTracker:
  # ================================================================================================
  # 초기화
  # ================================================================================================
  def __init__(self, progress_file: Path):
    # 진행률 파일 경로 저장
    self.progress_file = progress_file

    # 빈 진행률 파일 생성
    self._initialize_file()

  # ================================================================================================
  # 진행률 파일 초기화
  # ================================================================================================
  def _initialize_file(self) -> None:
    # 상위 디렉토리 보장
    self.progress_file.parent.mkdir(parents=True, exist_ok=True)

    # 빈 배열로 초기 상태 기록
    with self.progress_file.open("w", encoding=TEXT_FILE_ENCODING) as file:
      json.dump([], file)

  # ================================================================================================
  # 진행률 기록
  # ================================================================================================
  def track(self, percent: int, message: str) -> None:
    # 새 진행률 항목 생성
    entry: dict[str, Any] = {
      "percent": percent,
      "message": message,
      "timestamp": time.time(),
    }

    # 기존 기록 읽기
    try:
      if self.progress_file.exists():
        with self.progress_file.open(encoding=TEXT_FILE_ENCODING) as read_file:
          data: list[dict[str, Any]] = json.load(read_file)
      else:
        data = []
    except (json.JSONDecodeError, OSError):
      data = []

    # 새 항목 추가 후 파일 갱신
    data.append(entry)
    with self.progress_file.open("w", encoding=TEXT_FILE_ENCODING) as write_file:
      json.dump(data, write_file, ensure_ascii=False, indent=JSON_INDENT)

    # 콘솔 상태 출력 (로거로 대체)
    if percent >= 0:
      logger.info(f"[{PROGRESS_STATUS_SUCCESS}] {percent}%: {message}")
    else:
      logger.error(f"[{PROGRESS_STATUS_FAILED}] {percent}%: {message}")
