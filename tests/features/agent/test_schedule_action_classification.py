from typing import cast
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from app.features.agent.entity import ActionType
from app.features.agent.entity import AgentNodeName
from app.features.agent.schedules.nodes.classify_schedule_action import classify_schedule_action_node
from app.features.agent.state import RootState


@pytest.mark.asyncio
async def test_classify_schedule_action_node_uses_latest_user_action_keyword():
  """이전 안내 문구가 있어도 마지막 사용자 발화의 액션 키워드를 우선 분류해야 합니다."""
  state: RootState = {
    "messages": [
      HumanMessage(content="일정 작업좀 하자"),
      AIMessage(content="일정과 관련하여 어떤 작업을 도와드릴까요? 일정을 추가, 수정, 삭제하거나 조회할 수 있습니다."),
      HumanMessage(content="추가해줘"),
    ]
  }
  config = cast(RunnableConfig, {"configurable": {"thread_id": "test_thread"}})

  result = await classify_schedule_action_node(state, config)

  assert result.goto == AgentNodeName.EXTRACT_INFO.value
  assert (result.update or {}).get("action") == ActionType.ADD


@pytest.mark.asyncio
async def test_classify_schedule_action_node_falls_back_to_llm_without_explicit_keyword(mocker):
  """명시적 액션 키워드가 없으면 기존 LLM 분류 경로를 유지해야 합니다."""
  mock_chain = AsyncMock()
  mock_chain.ainvoke.return_value = AIMessage(content=ActionType.SEARCH.value)
  mocker.patch("app.features.agent.schedules.nodes.classify_schedule_action.get_llm")
  mocker.patch("app.features.agent.schedules.nodes.classify_schedule_action.apply_nostream", return_value=mock_chain)

  state: RootState = {
    "messages": [HumanMessage(content="내일 일정 좀 부탁해")],
  }
  config = cast(RunnableConfig, {"configurable": {"thread_id": "test_thread"}})

  result = await classify_schedule_action_node(state, config)

  assert result.goto == AgentNodeName.EXTRACT_INFO.value
  assert (result.update or {}).get("action") == ActionType.SEARCH
  mock_chain.ainvoke.assert_awaited_once()
