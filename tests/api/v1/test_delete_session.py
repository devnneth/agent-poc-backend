from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest

from app.api.common.jwt_request import jwt_required

MOCK_CLAIMS = {"sub": "user-8888", "exp": 9999999999}

SESSION_ID = "session-abc-123"


@pytest.fixture
def mock_jwt(app):
  """jwt_required Dependency를 모킹합니다."""
  app.dependency_overrides[jwt_required] = lambda: MOCK_CLAIMS
  yield
  app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_session_success(client, mock_jwt):
  """정상적으로 세션이 삭제될 때 200과 ok 응답을 반환합니다."""
  with patch(
    "app.infrastructure.persistence.checkpointer.checkpointer.delete_session",
    new_callable=AsyncMock,
  ) as mock_delete:
    response = await client.delete(f"/api/v1/agent/session/{SESSION_ID}")

  assert response.status_code == 200
  body = response.json()
  assert body["error"] is False
  assert body["result"]["session_id"] == SESSION_ID
  assert body["result"]["user_id"] == MOCK_CLAIMS["sub"]
  mock_delete.assert_awaited_once_with(SESSION_ID)


@pytest.mark.asyncio
async def test_delete_session_checkpointer_error(client, mock_jwt):
  """checkpointer 내부 오류 발생 시 500과 fail 응답을 반환합니다."""
  with patch(
    "app.infrastructure.persistence.checkpointer.checkpointer.delete_session",
    new_callable=AsyncMock,
    side_effect=RuntimeError("DB connection failed"),
  ):
    response = await client.delete(f"/api/v1/agent/session/{SESSION_ID}")

  assert response.status_code == 200  # CommonResponse는 항상 200으로 직렬화됨
  body = response.json()
  assert body["error"] is True
  assert body["status"] == 500
  assert "오류" in body["message"]


@pytest.mark.asyncio
async def test_delete_session_unauthorized(client, app):
  """Authorization 헤더 없이 요청하면 401을 반환합니다."""
  # jwt_required override 없이 실제 의존성 실행
  app.dependency_overrides.clear()
  response = await client.delete(
    f"/api/v1/agent/session/{SESSION_ID}",
    headers={"Content-Type": "application/json"},
  )
  assert response.status_code == 401


SESSION_IDS = ["session-abc-123", "session-def-456", "session-ghi-789"]


@pytest.mark.asyncio
async def test_delete_sessions_success(client, mock_jwt):
  """여러 세션을 일괄 삭제할 때 200과 ok 응답을 반환합니다."""
  with patch(
    "app.infrastructure.persistence.checkpointer.checkpointer.delete_sessions",
    new_callable=AsyncMock,
  ) as mock_delete:
    response = await client.request(
      "DELETE",
      "/api/v1/agent/sessions",
      json={"session_ids": SESSION_IDS},
    )

  assert response.status_code == 200
  body = response.json()
  assert body["error"] is False
  assert body["result"]["deleted_session_ids"] == SESSION_IDS
  assert body["result"]["user_id"] == MOCK_CLAIMS["sub"]
  mock_delete.assert_awaited_once_with(SESSION_IDS)


@pytest.mark.asyncio
async def test_delete_sessions_checkpointer_error(client, mock_jwt):
  """벌크 삭제 중 오류 발생 시 500과 fail 응답을 반환합니다."""
  with patch(
    "app.infrastructure.persistence.checkpointer.checkpointer.delete_sessions",
    new_callable=AsyncMock,
    side_effect=RuntimeError("DB connection failed"),
  ):
    response = await client.request(
      "DELETE",
      "/api/v1/agent/sessions",
      json={"session_ids": SESSION_IDS},
    )

  assert response.status_code == 200
  body = response.json()
  assert body["error"] is True
  assert body["status"] == 500
  assert "오류" in body["message"]
