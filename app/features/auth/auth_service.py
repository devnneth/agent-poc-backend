import logging
from typing import Any

from app.features.auth.auth_entity import AuthTokenResponse
from app.infrastructure.auth.google import GoogleAuth
from app.infrastructure.auth.supabase import SupabaseAuth


class AuthService:
  """인증 업무 로직을 관리하는 서비스 (Feature Layer)"""

  def __init__(self, auth_provider: SupabaseAuth, google_auth: GoogleAuth | None = None):
    self.auth_provider = auth_provider
    self.google_auth = google_auth
    self._logger = logging.getLogger(__name__)

  _instance = None

  @classmethod
  def get_instance(cls) -> "AuthService":
    if cls._instance is None:
      auth_provider = SupabaseAuth.get_instance()
      google_auth = GoogleAuth.get_instance()
      cls._instance = cls(auth_provider, google_auth)
    return cls._instance

  def login(self, email: str, password: str) -> AuthTokenResponse:
    return self.auth_provider.sign_in_with_password(email, password)

  def refresh_session(
    self,
    refresh_token: str,
    google_refresh_token: str | None = None,
  ) -> AuthTokenResponse:
    # 1. Supabase 세션 갱신
    response = self.auth_provider.refresh_session(refresh_token)

    # 2. Google 토큰 갱신 (있는 경우)
    if google_refresh_token and self.google_auth:
      try:
        new_google_access_token, expires_in = self.google_auth.refresh_access_token(
          google_refresh_token,
        )
        response.provider_token = new_google_access_token
        response.provider_expires_in = expires_in
      except Exception:
        self._logger.exception("Google token refresh failed")

    return response

  def verify_token(self, token: str) -> dict[str, Any]:
    return self.auth_provider.verify_access_token(token)


# _repo = SupabaseAuth(supabase)
# _google = GoogleAuth()
# auth_service = AuthService(_repo, _google)
