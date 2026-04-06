"""
1/5 단계 : 실행 환경 점검 서비스.

Docling 백엔드와 임베딩 필수 환경 변수 등을 검사한다.
"""

import os
from urllib import error as urllib_error
from urllib import request as urllib_request

from app.features.knowledge.processing.odlh_pipeline.config.contants import BACKEND_HEALTHCHECK_PATH
from app.features.knowledge.processing.odlh_pipeline.config.contants import BACKEND_NOT_RUNNING_MESSAGE
from app.features.knowledge.processing.odlh_pipeline.config.contants import BACKEND_REQUEST_TIMEOUT_SECONDS
from app.features.knowledge.processing.odlh_pipeline.config.contants import DEFAULT_HYBRID_BACKEND_URL
from app.features.knowledge.processing.odlh_pipeline.config.contants import HTTP_SUCCESS_STATUS_MAX
from app.features.knowledge.processing.odlh_pipeline.config.contants import HTTP_SUCCESS_STATUS_MIN
from app.features.knowledge.processing.odlh_pipeline.config.contants import OPENAI_API_KEY_ENV_VAR
from app.features.knowledge.processing.odlh_pipeline.config.contants import SUPPORTED_BACKEND_URL_SCHEMES


# ==================================================================================================
# 실행 환경 점검 서비스
# --------------------------------------------------------------------------------------------------
# 백엔드 연결 가능 여부를 점검하는 서비스
# ==================================================================================================
class EnvService:
  # ================================================================================================
  # 초기화
  # ================================================================================================
  def __init__(
    self,
    backend_url: str = DEFAULT_HYBRID_BACKEND_URL,
    timeout_seconds: float = BACKEND_REQUEST_TIMEOUT_SECONDS,
    api_key: str | None = None,
  ) -> None:
    # 백엔드 접속 정보 및 API 키 저장
    self.backend_url = backend_url
    self.timeout_seconds = timeout_seconds
    self.api_key = api_key

  # ================================================================================================
  # 백엔드 가용성 확인
  # ================================================================================================
  def is_backend_available(self) -> bool:
    # 지원하지 않는 URL 스킴 차단
    if not self.backend_url.startswith(SUPPORTED_BACKEND_URL_SCHEMES):
      return False

    # 헬스체크 엔드포인트 호출
    healthcheck_url = f"{self.backend_url.rstrip('/')}{BACKEND_HEALTHCHECK_PATH}"
    try:
      with urllib_request.urlopen(healthcheck_url, timeout=self.timeout_seconds) as response:  # noqa: S310
        return HTTP_SUCCESS_STATUS_MIN <= response.status < HTTP_SUCCESS_STATUS_MAX
    except (TimeoutError, OSError, ValueError, urllib_error.HTTPError, urllib_error.URLError):
      return False

  # ================================================================================================
  # 백엔드 필수 가용성 보장
  # ================================================================================================
  def ensure_backend_available(self) -> None:
    if self.is_backend_available():
      return

    healthcheck_url = f"{self.backend_url.rstrip('/')}{BACKEND_HEALTHCHECK_PATH}"
    raise ValueError(
      f"{BACKEND_NOT_RUNNING_MESSAGE} backend_url={self.backend_url} healthcheck_url={healthcheck_url} "
      "필요하면 ./scripts/rag-backend.sh 로 백엔드를 먼저 실행해 주세요."
    )

  # ================================================================================================
  # 임베딩 필수 환경 변수 확인
  # ================================================================================================
  def has_required_embedding_config(self) -> bool:
    # 주입된 API 키가 있으면 유효한 것으로 간주하고, 없으면 환경 변수를 확인한다.
    return bool(self.api_key or os.environ.get(OPENAI_API_KEY_ENV_VAR))
