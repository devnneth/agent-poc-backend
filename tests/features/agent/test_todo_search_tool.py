from datetime import UTC
from datetime import datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.types import Command

from app.features.agent.todo.tools.todo.search import SearchTodoInput
from app.features.agent.todo.tools.todo.search import search_todo_tool
from app.infrastructure.models.todo_model import TodoModel

typed_search_todo_tool = cast(StructuredTool, search_todo_tool)


@pytest.mark.asyncio
async def test_search_todo_tool_returns_command():
  """조회 결과가 Command 객체이며 todo_list를 업데이트해야 합니다."""
  todo_service = MagicMock()
  mock_todo = TodoModel(
    id=1,
    owner_user_id="user-1",
    title="미용실 가기",
    description="",
    status="TODO",
    priority="normal",
    project="",
    due_date=None,
    sort_order=0,
    created_at=datetime(2026, 3, 10, 9, 0, tzinfo=UTC),
    updated_at=datetime(2026, 3, 10, 9, 0, tzinfo=UTC),
    deleted_at=None,
    embedding_id=None,
  )
  todo_service.read_todos.return_value = [mock_todo]
  runtime = SimpleNamespace(
    config={
      "configurable": {
        "todo_service": todo_service,
        "user_id": "user-1",
      }
    },
    tool_call_id="tool-call-1",
  )

  # runtime 주입이 필요한 도구이므로 coroutine을 직접 호출해 검증
  tool_coroutine = typed_search_todo_tool.coroutine
  assert tool_coroutine is not None
  result_command = await tool_coroutine(
    input_data=SearchTodoInput(keyword=None, status=None, project=None),
    runtime=runtime,
  )

  assert isinstance(result_command, Command)
  assert result_command.update is not None
  assert result_command.update["todo_list"] == [mock_todo]
  assert len(result_command.update["messages"]) == 1
  assert isinstance(result_command.update["messages"][0], ToolMessage)
  todo_service.read_todos.assert_called_once()


@pytest.mark.asyncio
async def test_search_todo_tool_returns_empty_command_when_no_results():
  """검색 결과가 없을 때도 Command 객체를 반환하며 todo_list를 비워야 합니다."""
  todo_service = MagicMock()
  todo_service.read_todos.return_value = []
  runtime = SimpleNamespace(
    config={
      "configurable": {
        "todo_service": todo_service,
        "user_id": "user-1",
      }
    },
    tool_call_id="tool-call-2",
  )

  tool_coroutine = typed_search_todo_tool.coroutine
  assert tool_coroutine is not None
  result_command = await tool_coroutine(
    input_data=SearchTodoInput(keyword="없는 할일", status=None, project=None),
    runtime=runtime,
  )

  assert isinstance(result_command, Command)
  assert result_command.update is not None
  assert result_command.update["todo_list"] == []
  assert len(result_command.update["messages"]) == 1
  assert isinstance(result_command.update["messages"][0], ToolMessage)
