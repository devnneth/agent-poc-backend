from unittest.mock import MagicMock


def setup_mock_supabase_session(access_token="test-access", refresh_token="test-refresh"):
  """Supabase 세션 모킹을 위한 유틸리티 함수입니다."""
  mock_session = MagicMock()
  mock_session.access_token = access_token
  mock_session.refresh_token = refresh_token
  mock_session.token_type = "bearer"
  return mock_session


def setup_mock_supabase_auth_result(session=None, user=None):
  """Supabase Auth 결과 객체(session, user 포함)를 모킹합니다."""
  mock_result = MagicMock()
  mock_result.session = session
  mock_result.user = user
  return mock_result
