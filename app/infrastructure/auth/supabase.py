import logging
from typing import Any

import jwt
from cachetools import TTLCache

from app.core.config.environment import settings
from app.features.auth.auth_entity import AuthTokenResponse
from app.features.auth.auth_entity import UserPublic
from supabase import Client
from supabase import ClientOptions
from supabase import create_client

logger = logging.getLogger(__name__)


class SupabaseAuth:
  """Supabase를 사용하는 인증 서비스 (Infrastructure Layer)"""

  def __init__(self, client: Client):
    self._client = client
    # 인증 결과 캐시 (최대 1000개, 유효시간 5분)
    # 서버 RTT를 줄이기 위해 검증 성공 결과를 메모리에 저장합니다.
    self._verify_cache = TTLCache(maxsize=1000, ttl=300)

  _instance = None
  _client_instance: Client | None = None

  @classmethod
  def _get_client(cls) -> Client:
    """Supabase Client를 최초 1회만 생성하여 재사용합니다."""
    if cls._client_instance is None:
      logger.info("[%s] Supabase 연결 정보를 확인합니다.", settings.ENVIRONMENT.upper())
      logger.debug("Target URL: %s", settings.SUPABASE_URL)
      cls._client_instance = create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_KEY,
        options=ClientOptions(schema=settings.SUPABASE_SCHEMA),
      )
    return cls._client_instance

  @classmethod
  def get_instance(cls) -> "SupabaseAuth":
    if cls._instance is None:
      cls._instance = cls(cls._get_client())
    return cls._instance

  def sign_in_with_password(self, email: str, password: str) -> AuthTokenResponse:
    try:
      result = self._client.auth.sign_in_with_password({"email": email, "password": password})
      return self._build_token_response(result)
    except Exception as exc:
      logger.exception("Supabase sign_in_with_password failed")
      raise ValueError("로그인 처리 중 실패했습니다.") from exc

  def refresh_session(self, refresh_token: str) -> AuthTokenResponse:
    try:
      result = self._client.auth.refresh_session(refresh_token)
      return self._build_token_response(result)
    except Exception as exc:
      logger.exception("Supabase refresh_session failed")
      raise ValueError("토큰 갱신 중 실패했습니다.") from exc

  def verify_access_token(self, access_token: str) -> dict[str, Any]:
    """액세스 토큰의 유효성을 검증합니다.
    1. 캐시 확인 (5분 이내 동일 토큰 재사용 시 즉시 반환)
    2. HS256 알고리즘인 경우 로컬에서 즉시 검증 시도
    3. ES256 알고리즘인 경우 로컬에서 즉시 검증 시도
    4. 그 외 혹은 로컬 검증 실패 시 Supabase 서버를 통해 검증
    """
    # 1. 인메모리 캐시 확인
    if access_token in self._verify_cache:
      return self._verify_cache[access_token]

    result: dict[str, Any] = {"valid": False, "claims": None}
    try:
      header = jwt.get_unverified_header(access_token)
      alg = header.get("alg")
    except Exception:
      return result

    # 2 & 3. 로컬 검증 시도
    verified_payload = self._try_local_verify(access_token, alg)
    result = {"valid": True, "claims": verified_payload} if verified_payload else self._verify_via_server(access_token)

    if result.get("valid"):
      self._verify_cache[access_token] = result

    return result

  def _try_local_verify(self, token: str, alg: str | None) -> dict[str, Any] | None:
    """HS256 또는 ES256 알고리즘에 대해 로컬 검증을 시도합니다."""
    if alg == "HS256" and settings.SUPABASE_JWT_SECRET:
      try:
        return jwt.decode(
          token,
          settings.SUPABASE_JWT_SECRET,
          algorithms=["HS256"],
          audience="authenticated",
          options={"verify_exp": True},
        )
      except Exception:
        logger.debug("HS256 로컬 검증 실패")

    if alg == "ES256" and settings.SUPABASE_JWT_PUBLIC_KEY:
      try:
        return jwt.decode(
          token,
          settings.SUPABASE_JWT_PUBLIC_KEY,
          algorithms=["ES256"],
          audience="authenticated",
          options={"verify_exp": True},
        )
      except Exception:
        logger.debug("ES256 로컬 검증 실패")

    return None

  def _verify_via_server(self, token: str) -> dict[str, Any]:
    """Supabase 서버 API를 통해 토큰을 검증합니다."""
    try:
      response = self._client.auth.get_user(token)
      if response and response.user:
        payload = jwt.decode(token, options={"verify_signature": False})
        return {"valid": True, "claims": payload}
    except Exception as exc:
      logger.warning("Token verification via server failed: %s", str(exc))
    return {"valid": False, "claims": None}

  def _build_token_response(self, result: Any) -> AuthTokenResponse:
    session = getattr(result, "session", None)
    if not session:
      raise ValueError("세션 정보를 가져올 수 없습니다.")

    user = getattr(result, "user", None)
    user_public = None
    if user:
      user_public = UserPublic(id=user.id, email=user.email)

    return AuthTokenResponse(
      access_token=session.access_token,
      refresh_token=session.refresh_token,
      token_type=getattr(session, "token_type", "bearer"),
      expires_in=getattr(session, "expires_in", None),
      user=user_public,
    )
