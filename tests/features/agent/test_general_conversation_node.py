from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from app.features.agent.root.nodes.general_conversation import general_conversation_node
from app.features.agent.state import RootState


@pytest.mark.asyncio
async def test_general_conversation_node_refuses_domain_request_without_llm_call():
  """일반 대화 노드로 잘못 들어온 메모/할일/일정 요청은 추측 응답 없이 차단해야 합니다."""
  state: RootState = {
    "messages": [
      HumanMessage(content="메모 조회"),
    ],
  }
  config: RunnableConfig = {"configurable": {"thread_id": "test_thread"}}

  with patch("app.features.agent.root.nodes.general_conversation.get_llm", return_value=MagicMock()) as mock_get_llm:
    result = await general_conversation_node(state, config)

  assert result.update is not None
  assert "일반 대화로 처리할 수 없습니다" in result.update["messages"][0].content
  mock_get_llm.assert_not_called()
