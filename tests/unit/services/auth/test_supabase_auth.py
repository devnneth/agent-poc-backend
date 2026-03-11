from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from app.infrastructure.auth.supabase import SupabaseAuth as SupabaseAuthImpl
from tests.utils.mock_helpers import setup_mock_supabase_auth_result
from tests.utils.mock_helpers import setup_mock_supabase_session


@pytest.fixture
def auth_service(mock_supabase):
  """AuthService 인스턴스를 생성하는 피스처입니다."""
  service = SupabaseAuthImpl(mock_supabase)
  service._verify_cache.clear()
  return service


def test_sign_in_success(auth_service, mock_supabase):
  """성공적인 로그인 시나리오를 테스트합니다."""
  mock_session = setup_mock_supabase_session("access-123", "refresh-123")

  mock_user = MagicMock()
  mock_user.id = "user-123"
  mock_user.email = "test@example.com"

  mock_result = setup_mock_supabase_auth_result(session=mock_session, user=mock_user)

  mock_supabase.auth.sign_in_with_password.return_value = mock_result

  response = auth_service.sign_in_with_password("test@example.com", "password")

  assert response.access_token == "access-123"
  assert response.user.id == "user-123"
  mock_supabase.auth.sign_in_with_password.assert_called_once()


def test_refresh_token_success(auth_service, mock_supabase):
  """토큰 갱신 시나리오를 테스트합니다."""
  mock_session = setup_mock_supabase_session("new-access-123", "new-refresh-123")
  mock_result = setup_mock_supabase_auth_result(session=mock_session, user=None)

  mock_supabase.auth.refresh_session.return_value = mock_result

  response = auth_service.refresh_session("old-refresh-123")

  assert response.access_token == "new-access-123"
  assert response.refresh_token == "new-refresh-123"
  mock_supabase.auth.refresh_session.assert_called_once_with("old-refresh-123")


def test_verify_access_token_success(auth_service, mock_supabase):
  """액세스 토큰 검증 성공 시나리오를 테스트합니다 (HS256 로컬 검증)."""
  with (
    patch("jwt.get_unverified_header") as mock_header,
    patch("jwt.decode") as mock_decode,
    patch("app.infrastructure.auth.supabase.settings") as mock_settings,
  ):
    mock_header.return_value = {"alg": "HS256"}
    mock_decode.return_value = {"sub": "user-123", "email": "test@example.com"}
    mock_settings.SUPABASE_JWT_SECRET = "dummy-secret"

    result = auth_service.verify_access_token("valid-token")

    assert result["valid"] is True
    assert result["claims"]["sub"] == "user-123"
    mock_decode.assert_called_once()


def test_verify_access_token_server_fallback_success(auth_service, mock_supabase):
  """ES256 토큰이지만 공개키가 없는 상황 가정 (서버 fallback 발생)"""
  with (
    patch("jwt.get_unverified_header") as mock_header,
    patch("jwt.decode") as mock_decode,
    patch("app.infrastructure.auth.supabase.settings") as mock_settings,
  ):
    # ES256 토큰이지만 공개키가 없는 상황 가정 (서버 fallback 발생)
    mock_header.return_value = {"alg": "ES256"}
    mock_decode.return_value = {"sub": "server-user-123"}
    mock_settings.SUPABASE_JWT_PUBLIC_KEY = None

    # mock_supabase.auth.get_user 모킹
    mock_user = MagicMock()
    mock_user.id = "server-user-123"
    mock_supabase.auth.get_user.return_value.user = mock_user

    result = auth_service.verify_access_token("es256-token")

    assert result["valid"] is True
    assert result["claims"]["sub"] == "server-user-123"
    mock_supabase.auth.get_user.assert_called_once_with("es256-token")


def test_verify_access_token_es256_local_success(auth_service, mock_supabase):
  """ES256 토큰에 대해 공개키가 있을 때 로컬 검증으로 성공하는 시나리오를 테스트합니다."""
  with (
    patch("jwt.get_unverified_header") as mock_header,
    patch("jwt.decode") as mock_decode,
    patch("app.infrastructure.auth.supabase.settings") as mock_settings,
  ):
    mock_header.return_value = {"alg": "ES256"}
    mock_decode.return_value = {"sub": "es256-user-123"}
    mock_settings.SUPABASE_JWT_PUBLIC_KEY = "dummy-public-key"

    result = auth_service.verify_access_token("valid-es256-token")

    assert result["valid"] is True
    assert result["claims"]["sub"] == "es256-user-123"
    # 서버 호출 없이 로컬에서 끝나야 함
    mock_supabase.auth.get_user.assert_not_called()


def test_verify_access_token_failure(auth_service, mock_supabase):
  """모든 검증 시도가 실패했을 때를 테스트합니다."""
  with (
    patch("jwt.get_unverified_header") as mock_header,
    patch("app.infrastructure.auth.supabase.settings") as mock_settings,
  ):
    mock_header.return_value = {"alg": "HS256"}
    mock_settings.SUPABASE_JWT_SECRET = None
    mock_settings.SUPABASE_JWT_PUBLIC_KEY = None

    # 서버 응답도 유효하지 않게 설정
    mock_supabase.auth.get_user.return_value = None

    result = auth_service.verify_access_token("invalid-token")

    assert result["valid"] is False
    assert result["claims"] is None
