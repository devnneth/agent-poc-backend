import json
from datetime import date
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.types import Command

from app.api.common.request_entity import TodoPriority
from app.api.common.request_entity import TodoStatus
from app.features.agent.entity import IntentType
from app.features.agent.todo.prompts.tools.common import REJECTED_BY_USER_MESSAGE
from app.features.agent.todo.tools.todo.add import add_todo_tool
from app.features.todos.todo_dto import TodoCreate

typed_add_todo_tool = cast(StructuredTool, add_todo_tool)


@pytest.mark.asyncio
async def test_add_todo_tool_creates_todo_after_approval():
  """사용자가 승인하면 승인 후 데이터로 할일을 생성해야 합니다."""
  todo_service = MagicMock()
  todo_service.create_todo.return_value = SimpleNamespace(id=11, title="아침 운동하기")
  runtime = SimpleNamespace(
    config={
      "configurable": {
        "todo_service": todo_service,
        "user_id": "user-1",
      }
    },
    tool_call_id="tool-call-1",
  )
  input_data = TodoCreate(
    title="운동하기",
    description="헬스장 가기",
    status=TodoStatus.TODO,
    priority=TodoPriority.HIGH,
    project="건강",
    due_date=date(2026, 3, 20),
    sort_order=3,
  )
  mock_resume_data = {"messages": [MagicMock(content=json.dumps({"user_confirmed": "approve", "title": "아침 운동하기", "status": True}))]}

  tool_coroutine = typed_add_todo_tool.coroutine
  assert tool_coroutine is not None

  with patch("app.features.agent.todo.tools.todo.add.interrupt", return_value=mock_resume_data) as mock_interrupt:
    result_command = await tool_coroutine(input_data=input_data, runtime=runtime)

  assert isinstance(result_command, Command)
  assert result_command.update is not None
  assert isinstance(result_command.update["messages"][0], ToolMessage)
  todo_service.create_todo.assert_called_once()
  owner_user_id, payload = todo_service.create_todo.call_args.args
  assert owner_user_id == "user-1"
  assert payload.model_dump() == {
    "title": "아침 운동하기",
    "description": "헬스장 가기",
    "status": "DONE",
    "priority": "high",
    "project": "건강",
    "due_date": date(2026, 3, 20),
    "sort_order": 3,
  }

  interrupt_payload = mock_interrupt.call_args.args[0]
  assert interrupt_payload["intent"] == IntentType.TODO
  assert interrupt_payload["action"] == "add"
  assert interrupt_payload["todo_slots"] == {
    "title": "운동하기",
    "description": "헬스장 가기",
    "status": False,
    "priority": "high",
    "project": "건강",
  }


@pytest.mark.asyncio
async def test_add_todo_tool_returns_cancel_message_when_rejected():
  """사용자가 거절하면 생성하지 않고 취소 메시지를 반환해야 합니다."""
  todo_service = MagicMock()
  runtime = SimpleNamespace(
    config={
      "configurable": {
        "todo_service": todo_service,
        "user_id": "user-1",
      }
    },
    tool_call_id="tool-call-2",
  )
  input_data = TodoCreate(title="운동하기")
  mock_resume_data = {"messages": [MagicMock(content=json.dumps({"user_confirmed": "reject"}))]}

  tool_coroutine = typed_add_todo_tool.coroutine
  assert tool_coroutine is not None

  with patch("app.features.agent.todo.tools.todo.add.interrupt", return_value=mock_resume_data):
    result_command = await tool_coroutine(input_data=input_data, runtime=runtime)

  assert isinstance(result_command, Command)
  assert result_command.update is not None
  assert result_command.update["messages"][0].content == REJECTED_BY_USER_MESSAGE
  assert "HITL" not in result_command.update["messages"][0].content
  todo_service.create_todo.assert_not_called()
