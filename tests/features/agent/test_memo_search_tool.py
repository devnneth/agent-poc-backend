from datetime import UTC
from datetime import datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.types import Command

from app.features.agent.memo.tools.memo.search import SearchMemoInput
from app.features.agent.memo.tools.memo.search import search_memo_tool
from app.infrastructure.models.memo_model import MemoModel

typed_search_memo_tool = cast(StructuredTool, search_memo_tool)


@pytest.mark.asyncio
async def test_search_memo_tool_returns_command():
  """조회 결과가 Command 객체이며 memo_list를 업데이트해야 합니다."""
  memo_service = MagicMock()
  mock_memo = MemoModel(
    id=1,
    owner_user_id="user-1",
    title="회의 메모",
    content="안건 정리",
    created_at=datetime(2026, 3, 10, 9, 0, tzinfo=UTC),
    updated_at=datetime(2026, 3, 10, 9, 0, tzinfo=UTC),
    deleted_at=None,
    embedding_id=None,
  )
  memo_service.read_memos.return_value = [mock_memo]
  runtime = SimpleNamespace(
    config={
      "configurable": {
        "memo_service": memo_service,
        "user_id": "user-1",
      }
    },
    tool_call_id="tool-call-1",
  )

  tool_coroutine = typed_search_memo_tool.coroutine
  assert tool_coroutine is not None
  result_command = await tool_coroutine(
    input_data=SearchMemoInput(keyword=None),
    runtime=runtime,
  )

  assert isinstance(result_command, Command)
  assert result_command.update is not None
  assert result_command.update["memo_list"] == [mock_memo]
  assert len(result_command.update["messages"]) == 1
  assert isinstance(result_command.update["messages"][0], ToolMessage)
  memo_service.read_memos.assert_called_once()


@pytest.mark.asyncio
async def test_search_memo_tool_returns_empty_command_when_no_results():
  """검색 결과가 없을 때도 Command 객체를 반환하며 memo_list를 비워야 합니다."""
  memo_service = MagicMock()
  memo_service.read_memos.return_value = []
  runtime = SimpleNamespace(
    config={
      "configurable": {
        "memo_service": memo_service,
        "user_id": "user-1",
      }
    },
    tool_call_id="tool-call-2",
  )

  tool_coroutine = typed_search_memo_tool.coroutine
  assert tool_coroutine is not None
  result_command = await tool_coroutine(
    input_data=SearchMemoInput(keyword="없는 메모"),
    runtime=runtime,
  )

  assert isinstance(result_command, Command)
  assert result_command.update is not None
  assert result_command.update["memo_list"] == []
  assert len(result_command.update["messages"]) == 1
  assert isinstance(result_command.update["messages"][0], ToolMessage)
