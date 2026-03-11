import json
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.types import Command

from app.features.agent.entity import IntentType
from app.features.agent.memo.prompts.tools.common import REJECTED_BY_USER_MESSAGE
from app.features.agent.memo.tools.memo.add import add_memo_tool
from app.features.memos.memo_dto import MemoCreate

typed_add_memo_tool = cast(StructuredTool, add_memo_tool)


@pytest.mark.asyncio
async def test_add_memo_tool_creates_memo_after_approval():
  """사용자가 승인하면 승인 후 데이터로 메모를 생성해야 합니다."""
  memo_service = MagicMock()
  memo_service.create_memo.return_value = SimpleNamespace(id=21, title="회의 메모")
  runtime = SimpleNamespace(
    config={
      "configurable": {
        "memo_service": memo_service,
        "user_id": "user-1",
      }
    },
    tool_call_id="tool-call-1",
  )
  input_data = MemoCreate(
    title="회의",
    content="안건 정리",
  )
  mock_resume_data = {
    "messages": [MagicMock(content=json.dumps({"user_confirmed": "approve", "memo_slots": {"title": "회의 메모", "content": "안건 정리 및 액션 아이템"}}))]
  }

  tool_coroutine = typed_add_memo_tool.coroutine
  assert tool_coroutine is not None

  with patch("app.features.agent.memo.tools.memo.add.interrupt", return_value=mock_resume_data) as mock_interrupt:
    result_command = await tool_coroutine(input_data=input_data, runtime=runtime)

  assert isinstance(result_command, Command)
  assert result_command.update is not None
  assert isinstance(result_command.update["messages"][0], ToolMessage)
  memo_service.create_memo.assert_called_once()
  owner_user_id, payload = memo_service.create_memo.call_args.args
  assert owner_user_id == "user-1"
  assert payload.model_dump() == {
    "title": "회의 메모",
    "content": "안건 정리 및 액션 아이템",
  }

  interrupt_payload = mock_interrupt.call_args.args[0]
  assert interrupt_payload.intent == IntentType.MEMO
  assert interrupt_payload.action == "add"
  assert interrupt_payload.memo_slots.model_dump() == {
    "title": "회의",
    "content": "안건 정리",
    "memo_id": None,
    "query": None,
  }


@pytest.mark.asyncio
async def test_add_memo_tool_returns_cancel_message_when_rejected():
  """사용자가 거절하면 생성하지 않고 취소 메시지를 반환해야 합니다."""
  memo_service = MagicMock()
  runtime = SimpleNamespace(
    config={
      "configurable": {
        "memo_service": memo_service,
        "user_id": "user-1",
      }
    },
    tool_call_id="tool-call-2",
  )
  input_data = MemoCreate(title="회의", content="안건")
  mock_resume_data = {"messages": [MagicMock(content=json.dumps({"user_confirmed": "reject"}))]}

  tool_coroutine = typed_add_memo_tool.coroutine
  assert tool_coroutine is not None

  with patch("app.features.agent.memo.tools.memo.add.interrupt", return_value=mock_resume_data):
    result_command = await tool_coroutine(input_data=input_data, runtime=runtime)

  assert isinstance(result_command, Command)
  assert result_command.update is not None
  assert result_command.update["messages"][0].content == REJECTED_BY_USER_MESSAGE
  memo_service.create_memo.assert_not_called()
