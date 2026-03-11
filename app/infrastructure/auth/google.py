import logging

import httpx

from app.core.config.environment import settings

logger = logging.getLogger(__name__)


class GoogleAuthError(Exception):
  """구글 인증 관련 예외"""

  def __init__(self, message: str, status_code: int = 500):
    super().__init__(message)
    self.status_code = status_code


class GoogleAuth:
  """Google API 연동을 담당하는 구현체 (Infrastructure Layer)"""

  _instance = None

  @classmethod
  def get_instance(cls) -> "GoogleAuth":
    if cls._instance is None:
      cls._instance = cls()
    return cls._instance

  def refresh_access_token(self, google_refresh_token: str) -> tuple[str, int]:
    """구글 리프레시 토큰을 사용하여 새로운 액세스 토큰을 받아옵니다."""
    client_id = settings.GOOGLE_CLIENT_ID
    client_secret = settings.GOOGLE_CLIENT_SECRET

    if not client_id or not client_secret:
      logger.error("Google OAuth configuration is missing")
      raise GoogleAuthError("구글 OAuth 설정이 누락되었습니다.", status_code=500)

    url = "https://oauth2.googleapis.com/token"
    data = {
      "client_id": client_id,
      "client_secret": client_secret,
      "refresh_token": google_refresh_token,
      "grant_type": "refresh_token",
    }

    try:
      with httpx.Client() as client:
        response = client.post(url, data=data)
        response.raise_for_status()
        token_data = response.json()

        access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in")

        if not access_token:
          raise GoogleAuthError("구글 액세스 토큰을 받지 못했습니다.", status_code=500)

        return str(access_token), int(expires_in or 3600)
    except httpx.HTTPStatusError as exc:
      logger.exception("Google token refresh failed with status %s", exc.response.status_code)
      raise GoogleAuthError(
        f"구글 토큰 갱신에 실패했습니다: {exc.response.text}",
        status_code=exc.response.status_code,
      ) from exc
    except Exception as exc:
      logger.exception("Google token refresh failed")
      raise GoogleAuthError(
        "구글 토큰 갱신 중 예기치 않은 오류가 발생했습니다.",
        status_code=500,
      ) from exc
