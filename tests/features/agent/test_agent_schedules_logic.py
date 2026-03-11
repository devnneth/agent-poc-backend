from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage

from app.features.agent.entity import ActionType
from app.features.agent.entity import HITLResultType
from app.features.agent.entity import ScheduleExtractedInfo
from app.features.agent.schedules.nodes.execute_tool import execute_tool_node
from app.features.agent.state import RootState


@pytest.mark.asyncio
async def test_execute_tool_node_state_reset(mocker):
  """도구 실행 성공 후 상태가 초기화되는지 확인합니다."""
  from typing import cast

  from langchain_core.runnables import RunnableConfig
  from langgraph.types import Command

  mock_add = mocker.patch("app.features.agent.schedules.nodes.execute_tool.add_schedule")
  mock_add.ainvoke = AsyncMock(return_value="일정이 추가되었습니다.")

  state: RootState = {
    "action": ActionType.ADD,
    "schedule_slots": ScheduleExtractedInfo(summary="테스트 회의", start_at="2026-02-28T10:00:00"),
    "user_confirmed": HITLResultType.APPROVE,
    "messages": [HumanMessage(content="내일 10시 회의 추가해줘")],
  }

  config = cast(RunnableConfig, {"configurable": {"thread_id": "test_thread"}})

  result = await execute_tool_node(state, config)

  # execute_tool_node는 이제 Command를 반환합니다
  assert isinstance(result, Command)
  upd = result.update or {}
  assert upd.get("action") is None
  assert upd.get("schedule_slots") is None
  assert upd.get("user_confirmed") is None
  # delete_result 등을 확인

  messages = upd.get("messages", [])
  assert len(messages) > 0
  assert isinstance(messages[0], AIMessage)
  assert "일정이 추가되었습니다." in messages[0].content


@pytest.mark.asyncio
async def test_execute_tool_node_returns_short_rejection_message():
  """승인이 거절되면 짧은 취소 메시지로 종료해야 합니다."""
  from typing import cast

  from langchain_core.runnables import RunnableConfig
  from langgraph.types import Command

  state: RootState = {
    "action": ActionType.DELETE,
    "schedule_slots": ScheduleExtractedInfo(schedule_id=1),
    "user_confirmed": HITLResultType.REJECT,
    "messages": [HumanMessage(content="삭제하지 마")],
  }

  config = cast(RunnableConfig, {"configurable": {"thread_id": "test_thread"}})

  result = await execute_tool_node(state, config)

  assert isinstance(result, Command)
  assert result.goto == "final_response_node"
  assert result.update is not None
  messages = result.update["messages"]
  assert len(messages) == 1
  assert isinstance(messages[0], AIMessage)
  assert messages[0].content == "요청 취소"
