import json
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from app.api.common.jwt_request import jwt_required

MOCK_CLAIMS = {"sub": "user-8888", "exp": 9999999999}


# ==================================================================================================
# JWT 의존성 모킹
# --------------------------------------------------------------------------------------------------
# 지식 도구 테스트를 위해 API 인증 과정을 가짜 객체로 대체함
# ==================================================================================================
@pytest.fixture
def mock_jwt(app):
  app.dependency_overrides[jwt_required] = lambda: MOCK_CLAIMS
  yield
  app.dependency_overrides.clear()


# ==================================================================================================
# 지식 도구 로드 이벤트 테스트
# --------------------------------------------------------------------------------------------------
# 지식 검색 도구가 로드될 때 발생하는 커스텀 이벤트가 SSE를 통해 전송되는지 검증함
# ==================================================================================================
@pytest.mark.asyncio
async def test_chat_stream_includes_knowledge_tool_loaded_event(client, mock_jwt):
  # ------------------------------------------------------------------------------------------------
  # 지식 도구 이벤트 모킹
  # ------------------------------------------------------------------------------------------------
  async def mock_astream_events(*args, **kwargs):
    yield {
      "event": "on_custom_event",
      "data": {
        "message": "knowledge 도구 2개를 불러왔습니다.",
        "tool_titles": ["프로덕트 문서", "개발 위키"],
        "count": 2,
        "cache_hit": False,
        "version": "v1",
      },
      "metadata": {"node": "general_conversation_node"},
      "tags": [],
      "name": "knowledge_tools_loaded",
    }

  mock_graph_obj = MagicMock()
  mock_graph_obj.aget_state = AsyncMock(return_value=MagicMock(next=()))
  mock_graph_obj.astream_events = mock_astream_events

  with patch("app.api.v1.agent.chat.get_router_graph", return_value=mock_graph_obj):
    payload = {
      "user_id": "test-user",
      "session_id": "test-session",
      "calendar_id": "test-calendar",
      "message": "문서 참고해서 답해줘",
      "language": "ko",
      "google_calendar_token": "token",
    }

    response = await client.post("/api/v1/agent/chat", json=payload)

  assert response.status_code == 200

  chunks = []
  async for line in response.aiter_lines():
    if line.startswith("data: "):
      chunks.append(line[6:])

  payloads = [json.loads(chunk) for chunk in chunks]
  tool_payload = next(payload for payload in payloads if payload["category"] == "hitl")

  assert tool_payload["content"] == ""
  assert tool_payload["metadata"]["node"] == "general_conversation_node"
