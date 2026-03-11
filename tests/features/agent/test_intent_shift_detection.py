from typing import cast
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from app.features.agent.entity import ActionType
from app.features.agent.entity import AgentNodeName
from app.features.agent.entity import IntentShiftResult
from app.features.agent.entity import ScheduleExtractedInfo
from app.features.agent.schedules.nodes.check_information.common import _detect_intent_shift
from app.features.agent.schedules.nodes.intent_shift import intent_shift_node
from app.features.agent.state import RootState


@pytest.mark.asyncio
async def test_detect_intent_shift_returns_false(mocker):
  """요청된 정보를 제공하는 응답에서 is_shifted=False를 반환하는지 확인합니다."""
  mock_chain = AsyncMock()
  mock_chain.ainvoke.return_value = IntentShiftResult(is_shifted=False)
  mocker.patch("app.features.agent.schedules.nodes.check_information.common.get_llm").return_value.with_structured_output.return_value = AsyncMock()
  mocker.patch("app.features.agent.schedules.nodes.check_information.common.apply_nostream", return_value=mock_chain)

  state: RootState = {
    "messages": [HumanMessage(content="내일 오후 3시요")],
    "action": ActionType.ADD,
  }
  config = cast(RunnableConfig, {"configurable": {"thread_id": "test"}})

  result = await _detect_intent_shift(state["messages"], config, ActionType.ADD, ScheduleExtractedInfo(summary="회의"), "시작 시간을 알려주세요")

  assert result is False


@pytest.mark.asyncio
async def test_detect_intent_shift_returns_true(mocker):
  """다른 작업으로 전환하는 응답에서 is_shifted=True를 반환하는지 확인합니다."""
  mock_chain = AsyncMock()
  mock_chain.ainvoke.return_value = IntentShiftResult(is_shifted=True)
  mocker.patch("app.features.agent.schedules.nodes.check_information.common.get_llm").return_value.with_structured_output.return_value = AsyncMock()
  mocker.patch("app.features.agent.schedules.nodes.check_information.common.apply_nostream", return_value=mock_chain)

  state: RootState = {
    "messages": [HumanMessage(content="그냥 내일 일정 조회해줘")],
    "action": ActionType.ADD,
  }
  config = cast(RunnableConfig, {"configurable": {"thread_id": "test"}})

  result = await _detect_intent_shift(state["messages"], config, ActionType.ADD, ScheduleExtractedInfo(summary="회의"), "시작 시간을 알려주세요")

  assert result is True


@pytest.mark.asyncio
async def test_intent_shift_node_resets_state():
  """intent_shift_node 호출 시 상태가 초기화되고 ROOT_INTENT로 이동하는지 확인합니다."""
  state: RootState = {
    "action": ActionType.ADD,
    "schedule_slots": ScheduleExtractedInfo(summary="테스트 회의"),
    "user_confirmed": None,
    "messages": [HumanMessage(content="이전 대화")],
  }
  config = cast(RunnableConfig, {"configurable": {"thread_id": "test"}})

  result = await intent_shift_node(state, config)

  assert isinstance(result, Command)
  assert result.goto == AgentNodeName.ROOT_INTENT.value
  assert result.graph == Command.PARENT

  updates = result.update or {}
  assert updates.get("action") is None
  assert updates.get("schedule_slots") == {}
  assert updates.get("user_confirmed") is None
