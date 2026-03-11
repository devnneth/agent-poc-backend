from datetime import UTC
from datetime import datetime
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi import Request
from freezegun import freeze_time

from app.api.common.jwt_request import jwt_required


@pytest.fixture
def mock_request():
  """테스트를 위한 FastAPI Request 객체 모킹 피스처입니다."""
  request = MagicMock(spec=Request)
  request.state = MagicMock()
  return request


@freeze_time("2024-01-01 12:00:00")
def test_jwt_required_success(mock_request, monkeypatch):
  """유효한 JWT 토큰이 제공되었을 때 인증이 성공하는지 테스트합니다."""
  # auth_service.verify_access_token 모킹
  future_exp = int((datetime.now(UTC) + timedelta(hours=1)).timestamp())
  mock_claims = {"exp": future_exp, "sub": "user-123"}

  mock_auth_service = MagicMock()
  mock_auth_service.verify_token.return_value = {"valid": True, "claims": mock_claims}
  monkeypatch.setattr("app.api.common.jwt_request.AuthService.get_instance", lambda: mock_auth_service)

  result = jwt_required(mock_request, authorization="Bearer valid-token")

  assert result == mock_claims
  assert mock_request.state.claims == mock_claims
  mock_auth_service.verify_token.assert_called_once_with("valid-token")


def test_jwt_required_no_header(mock_request):
  """Authorization 헤더가 없을 때 401 에러를 발생하는지 테스트합니다."""
  with pytest.raises(HTTPException) as exc:
    jwt_required(mock_request, authorization=None)
  assert exc.value.status_code == 401
  assert "Authorization 헤더가 필요합니다" in exc.value.detail


def test_jwt_required_invalid_token(mock_request, monkeypatch):
  """유효하지 않은 토큰일 때 401 에러를 발생하는지 테스트합니다."""
  mock_auth_service = MagicMock()
  mock_auth_service.verify_token.return_value = {"valid": False}
  monkeypatch.setattr("app.api.common.jwt_request.AuthService.get_instance", lambda: mock_auth_service)

  with pytest.raises(HTTPException) as exc:
    jwt_required(mock_request, authorization="Bearer invalid-token")
  assert exc.value.status_code == 401
  assert "유효하지 않은 access_token" in exc.value.detail


@freeze_time("2024-01-01 12:00:00")
def test_jwt_required_expired_token(mock_request, monkeypatch):
  """만료된 토큰일 때 401 에러를 발생하는지 테스트합니다."""
  past_exp = int((datetime.now(UTC) - timedelta(hours=1)).timestamp())
  mock_claims = {"exp": past_exp, "sub": "user-123"}

  mock_auth_service = MagicMock()
  mock_auth_service.verify_token.return_value = {"valid": True, "claims": mock_claims}
  monkeypatch.setattr("app.api.common.jwt_request.AuthService.get_instance", lambda: mock_auth_service)

  with pytest.raises(HTTPException) as exc:
    jwt_required(mock_request, authorization="Bearer expired-token")
  assert exc.value.status_code == 401
  assert "access_token이 만료되었습니다" in exc.value.detail


def test_jwt_required_missing_sub(mock_request, monkeypatch):
  """claims에 sub가 없을 때 401 에러를 발생하는지 테스트합니다."""
  future_exp = int((datetime.now(UTC) + timedelta(hours=1)).timestamp())
  mock_claims = {"exp": future_exp}  # sub missing

  mock_auth_service = MagicMock()
  mock_auth_service.verify_token.return_value = {"valid": True, "claims": mock_claims}
  monkeypatch.setattr("app.api.common.jwt_request.AuthService.get_instance", lambda: mock_auth_service)

  with pytest.raises(HTTPException) as exc:
    jwt_required(mock_request, authorization="Bearer valid-token")
  assert exc.value.status_code == 401
  assert "사용자 식별자(sub)를 찾을 수 없습니다" in exc.value.detail
