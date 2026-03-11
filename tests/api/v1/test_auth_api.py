from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from tests.utils.mock_helpers import setup_mock_supabase_auth_result
from tests.utils.mock_helpers import setup_mock_supabase_session


@pytest.mark.asyncio
async def test_api_login_success(client: AsyncClient, mock_supabase):
  """API를 통한 로그인 성공 시나리오를 테스트합니다."""
  mock_session = setup_mock_supabase_session("api-access-123", "api-refresh-123")

  mock_user = MagicMock()
  mock_user.id = "api-user-123"
  mock_user.email = "api-test@example.com"

  mock_result = setup_mock_supabase_auth_result(session=mock_session, user=mock_user)

  mock_supabase.auth.sign_in_with_password.return_value = mock_result

  payload = {"email": "api-test@example.com", "password": "password123"}

  response = await client.post("/api/v1/auth/login", json=payload)

  assert response.status_code == 200
  data = response.json()
  assert data["result"]["access_token"] == "api-access-123"


@pytest.mark.asyncio
async def test_api_verify_token_success(client: AsyncClient, mock_supabase):
  """API를 통한 토큰 검증 성공 시나리오를 테스트합니다."""
  # jwt.decode와 jwt.get_unverified_header를 patch하여 유효한 토큰으로 위장
  with patch("jwt.get_unverified_header") as mock_header, patch("jwt.decode") as mock_decode:
    mock_header.return_value = {"alg": "HS256"}
    mock_decode.return_value = {"sub": "api-user-123", "aud": "authenticated"}

    # SupabaseAuth 인스턴스를 가져와서 캐시가 비어있음을 보장하거나 강제로 모킹
    from app.infrastructure.auth.supabase import SupabaseAuth

    auth = SupabaseAuth.get_instance()
    auth._verify_cache.clear()

    # 서버 사이드 검증 fallback을 위해 get_user 모킹
    mock_user = MagicMock()
    mock_user.id = "api-user-123"
    mock_supabase.auth.get_user.return_value.user = mock_user

    response = await client.post("/api/v1/auth/verify", params={"access_token": "valid-api-token"})

    assert response.status_code == 200
    data = response.json()
    assert data["result"] is True


@pytest.mark.asyncio
async def test_api_refresh_token_success(client: AsyncClient, mock_supabase):
  """API를 통한 토큰 갱신 성공 시나리오를 테스트합니다 (Supabase만)."""
  mock_session = setup_mock_supabase_session("api-new-access", "api-new-refresh")
  mock_result = setup_mock_supabase_auth_result(session=mock_session, user=None)

  mock_supabase.auth.refresh_session.return_value = mock_result

  response = await client.post("/api/v1/auth/refresh", json={"refresh_token": "api-old-refresh"})

  assert response.status_code == 200
  data = response.json()
  assert data["result"]["access_token"] == "api-new-access"
  assert "provider_token" not in data["result"] or data["result"]["provider_token"] is None


@pytest.mark.asyncio
async def test_api_refresh_with_google_success(client: AsyncClient, mock_supabase):
  """API를 통한 통합 토큰 갱신 성공 시나리오를 테스트합니다 (Supabase + Google)."""
  # 1. Supabase 모킹
  mock_session = setup_mock_supabase_session("sb-access-456", "sb-refresh-456")
  mock_result = setup_mock_supabase_auth_result(session=mock_session, user=None)
  mock_supabase.auth.refresh_session.return_value = mock_result

  # 2. Google 모킹 (auth_service.google_auth 내부 메서드)
  from app.features.auth.auth_service import AuthService

  with patch.object(
    AuthService.get_instance().google_auth,
    "refresh_access_token",
  ) as mock_google_refresh:
    mock_google_refresh.return_value = ("google-access-456", 3600)

    payload = {"refresh_token": "sb-old-refresh", "google_refresh_token": "google-old-refresh"}

    response = await client.post("/api/v1/auth/refresh", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["result"]["access_token"] == "sb-access-456"
    assert data["result"]["provider_token"] == "google-access-456"
    assert data["result"]["provider_expires_in"] == 3600
    mock_google_refresh.assert_called_once_with("google-old-refresh")


@pytest.mark.asyncio
async def test_api_login_invalid_payload(client: AsyncClient):
  """잘못된 페이로드 전달 시 422 에러가 발생하는지 테스트합니다."""
  payload = {
    "email": "not-an-email",
    # password 누락
  }

  response = await client.post("/api/v1/auth/login", json=payload)
  assert response.status_code == 422
