from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessageChunk

from app.api.common.jwt_request import jwt_required
from app.api.common.response_entity import AgentResponseSSECategory
from app.features.agent.entity import HITLInterruptData
from app.features.agent.entity import IntentType
from app.infrastructure.common.exceptions import LLMQuotaError

MOCK_CLAIMS = {"sub": "user-8888", "exp": 9999999999}


@pytest.fixture
def mock_jwt(app):
  """jwt_required Dependency를 모킹합니다."""
  app.dependency_overrides[jwt_required] = lambda: MOCK_CLAIMS
  yield
  app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_llm_quota_error(client, mock_jwt):
  """LLM 쿼터 에러 발생 시 사용자 친화적인 메시지와 상세 메타데이터가 포함되는지 테스트합니다."""

  async def mock_astream_error(*args, **kwargs):
    # 비동기 제너레이터 내에서 에러 발생
    raise LLMQuotaError("Quota exceeded", status_code=429, response_body='{"error": "insufficient_quota"}')
    yield  # 제너레이터로 인식되게 함

  mock_graph_obj = MagicMock()
  mock_graph_obj.aget_state = AsyncMock(return_value=MagicMock(next=()))
  mock_graph_obj.astream_events = mock_astream_error

  with patch("app.api.v1.agent.chat.get_router_graph", return_value=mock_graph_obj):
    payload = {
      "user_id": "test-user",
      "session_id": "test-session",
      "calendar_id": "test-calendar",
      "message": "hello",
      "language": "ko",
      "google_calendar_token": "token",
    }

    response = await client.post("/api/v1/agent/chat", json=payload)

    assert response.status_code == 200

    chunks = []
    async for line in response.aiter_lines():
      if line.startswith("data: "):
        chunks.append(line[6:])

    assert len(chunks) > 0
    import json

    error_payload = json.loads(chunks[0])

    assert error_payload["type"] == "data"
    assert error_payload["category"] == "error"
    assert "쿼터(잔액)가 부족합니다" in error_payload["content"]
    assert error_payload["metadata"]["detail"] == '{"error": "insufficient_quota"}'
    assert "Quota exceeded" in error_payload["metadata"]["error"]


@pytest.mark.asyncio
async def test_chat_generic_error(client, mock_jwt):
  """일반적인 에러 발생 시 기본 메시지와 에러 내용이 포함되는지 테스트합니다."""

  async def mock_astream_generic_error(*args, **kwargs):
    raise RuntimeError("Something went wrong")
    yield

  mock_graph_obj = MagicMock()
  mock_graph_obj.aget_state = AsyncMock(return_value=MagicMock(next=()))
  mock_graph_obj.astream_events = mock_astream_generic_error

  with patch("app.api.v1.agent.chat.get_router_graph", return_value=mock_graph_obj):
    payload = {
      "user_id": "test-user",
      "session_id": "test-session",
      "calendar_id": "test-calendar",
      "message": "hello",
      "language": "ko",
      "google_calendar_token": "token",
    }

    response = await client.post("/api/v1/agent/chat", json=payload)

    assert response.status_code == 200

    chunks = []
    async for line in response.aiter_lines():
      if line.startswith("data: "):
        chunks.append(line[6:])

    import json

    error_payload = json.loads(chunks[0])

    assert error_payload["category"] == "error"
    assert "에이전트 실행 중 오류가 발생했습니다" in error_payload["content"]
    assert error_payload["metadata"]["error"] == "Something went wrong"


@pytest.mark.asyncio
async def test_chat_stream_does_not_duplicate_final_message(client, mock_jwt):
  """스트리밍 청크가 이미 전달된 경우 종료 이벤트에서 본문이 중복되지 않아야 합니다."""

  async def mock_astream_events(*args, **kwargs):
    yield {
      "event": "on_chat_model_start",
      "data": {},
      "metadata": {"node": "todo_agent"},
      "tags": [],
      "name": "ChatOpenAI",
    }
    yield {
      "event": "on_chat_model_stream",
      "data": {"chunk": AIMessageChunk(content="현재 할일 목록입니다.")},
      "metadata": {"node": "todo_agent"},
      "tags": [],
      "name": "ChatOpenAI",
    }
    yield {
      "event": "on_chat_model_end",
      "data": {"output": AIMessageChunk(content="현재 할일 목록입니다.")},
      "metadata": {"node": "todo_agent"},
      "tags": [],
      "name": "ChatOpenAI",
    }

  mock_graph_obj = MagicMock()
  mock_graph_obj.aget_state = AsyncMock(return_value=MagicMock(next=()))
  mock_graph_obj.astream_events = mock_astream_events

  with patch("app.api.v1.agent.chat.get_router_graph", return_value=mock_graph_obj):
    payload = {
      "user_id": "test-user",
      "session_id": "test-session",
      "calendar_id": "test-calendar",
      "message": "할일 보여줘",
      "language": "ko",
      "google_calendar_token": "token",
    }

    response = await client.post("/api/v1/agent/chat", json=payload)

    assert response.status_code == 200

    chunks = []
    async for line in response.aiter_lines():
      if line.startswith("data: "):
        chunks.append(line[6:])

    import json

    payloads = [json.loads(chunk) for chunk in chunks]
    message_payloads = [payload for payload in payloads if payload["category"] == "message"]

    assert len(message_payloads) == 2
    assert message_payloads[0]["status"] == "ing"
    assert message_payloads[0]["content"] == "현재 할일 목록입니다."
    assert message_payloads[1]["status"] == "end"
    assert message_payloads[1]["content"] == ""


@pytest.mark.asyncio
async def test_chat_interrupt_payload_includes_intent_metadata(client, mock_jwt):
  """HITL interrupt payload의 intent가 SSE metadata로 전달되어야 합니다."""

  async def mock_astream_events(*args, **kwargs):
    yield {
      "event": "on_custom_event",
      "data": {
        "__interrupt__": [
          MagicMock(
            value=HITLInterruptData(
              category=AgentResponseSSECategory.HITL,
              message="할일 추가 작업을 승인해주세요",
              intent=IntentType.TODO,
            ).model_dump(exclude_none=True)
          )
        ]
      },
      "metadata": {"node": "todo_agent"},
      "tags": ["hitl"],
      "name": "interrupt",
    }

  mock_graph_obj = MagicMock()
  mock_graph_obj.aget_state = AsyncMock(return_value=MagicMock(next=()))
  mock_graph_obj.astream_events = mock_astream_events

  with patch("app.api.v1.agent.chat.get_router_graph", return_value=mock_graph_obj):
    payload = {
      "user_id": "test-user",
      "session_id": "test-session",
      "calendar_id": "test-calendar",
      "message": "할일 추가해줘",
      "language": "ko",
      "google_calendar_token": "token",
    }

    response = await client.post("/api/v1/agent/chat", json=payload)

    assert response.status_code == 200

    chunks = []
    async for line in response.aiter_lines():
      if line.startswith("data: "):
        chunks.append(line[6:])

    import json

    payloads = [json.loads(chunk) for chunk in chunks]
    hitl_payload = next(payload for payload in payloads if payload["category"] == "hitl")

  assert hitl_payload["content"] == "할일 추가 작업을 승인해주세요"
  assert hitl_payload["metadata"]["intent"] == "todo"
