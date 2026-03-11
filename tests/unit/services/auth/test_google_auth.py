from unittest.mock import MagicMock
from unittest.mock import PropertyMock
from unittest.mock import patch

import httpx
import pytest

from app.infrastructure.auth.google import GoogleAuth as GoogleAuthImpl
from app.infrastructure.auth.google import GoogleAuthError


@pytest.fixture
def google_auth():
  return GoogleAuthImpl()


def test_google_refresh_token_success(google_auth):
  """구글 토큰 갱신 성공 시나리오 테스트"""
  mock_response = MagicMock()
  mock_response.status_code = 200
  mock_response.json.return_value = {"access_token": "new-google-access", "expires_in": 3600}
  mock_response.raise_for_status = MagicMock()

  with patch("httpx.Client.post", return_value=mock_response):
    token, expires = google_auth.refresh_access_token("old-google-refresh")

    assert token == "new-google-access"
    assert expires == 3600


def test_google_refresh_token_http_error(google_auth):
  """구글 토큰 갱신 HTTP 에러 시나리오 테스트"""
  mock_response = MagicMock()
  mock_response.status_code = 401
  mock_response.text = "Unauthorized"

  # raise_for_status를 호출할 때 HTTPStatusError가 발생하도록 설정
  error = httpx.HTTPStatusError("Auth error", request=MagicMock(), response=mock_response)
  mock_response.raise_for_status.side_effect = error

  with patch("httpx.Client.post", return_value=mock_response):
    with pytest.raises(GoogleAuthError) as excinfo:
      google_auth.refresh_access_token("invalid-refresh")

    assert excinfo.value.status_code == 401
    assert "구글 토큰 갱신에 실패했습니다" in str(excinfo.value)


def test_google_refresh_token_unexpected_error(google_auth):
  """구글 토큰 갱신 예기치 않은 에러 시나리오 테스트"""
  with patch("httpx.Client.post", side_effect=Exception("Network error")):
    with pytest.raises(GoogleAuthError) as excinfo:
      google_auth.refresh_access_token("any-refresh")

    assert excinfo.value.status_code == 500
    assert "예기치 않은 오류" in str(excinfo.value)


def test_google_refresh_token_missing_config(google_auth):
  """설정 누락 시 에러 발생 테스트"""
  from app.infrastructure.auth.google import settings

  with patch.object(type(settings), "GOOGLE_CLIENT_ID", new_callable=PropertyMock) as mock_id:
    mock_id.return_value = None
    with pytest.raises(GoogleAuthError) as excinfo:
      google_auth.refresh_access_token("any-refresh")
    assert "설정이 누락되었습니다" in str(excinfo.value)
