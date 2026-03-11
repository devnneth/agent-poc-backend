import logging
from typing import Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command
from langgraph.types import interrupt

from app.api.common.response_entity import AgentResponseSSECategory
from app.features.agent.entity import ActionType
from app.features.agent.entity import HITLInterruptData
from app.features.agent.entity import HITLResultType
from app.features.agent.entity import IntentType
from app.features.agent.entity import MemoExtractedInfo
from app.features.agent.helpers.graph_helpers import parse_memo_confirmation
from app.features.agent.memo.prompts.tools.add import DESCRIPTION
from app.features.agent.memo.prompts.tools.common import REJECTED_BY_USER_MESSAGE
from app.features.agent.state import RootState
from app.features.memos.memo_dto import MemoCreate
from app.features.memos.memo_service import MemoService

logger = logging.getLogger(__name__)


def _build_tool_message(runtime: ToolRuntime[Any, RootState], content: str) -> ToolMessage:
  """현재 tool call에 연결된 응답 메시지를 생성합니다."""
  return ToolMessage(content=content, tool_call_id=runtime.tool_call_id)


def _get_runtime_dependencies(runtime: ToolRuntime[Any, RootState]) -> tuple[MemoService | None, str | None]:
  """ToolRuntime에서 add_memo_tool 실행에 필요한 의존성을 추출합니다."""
  configurable = runtime.config.get("configurable") or {}
  memo_service = configurable.get("memo_service")
  owner_user_id = configurable.get("user_id")
  return memo_service, owner_user_id


def _build_memo_slots(input_data: MemoCreate) -> MemoExtractedInfo:
  """추가 승인 화면에서 바로 확인/수정할 수 있도록 입력값을 memo_slots로 변환합니다."""
  return MemoExtractedInfo(
    title=input_data.title,
    content=input_data.content,
  )


@tool(description=DESCRIPTION)
async def add_memo_tool(input_data: MemoCreate, runtime: ToolRuntime[None, RootState]) -> Command:
  """새로운 메모를 추가합니다. 추가 전에는 반드시 HITL 승인을 받습니다."""
  logger.info("Adding new memo: title=%s", input_data.title)
  memo_service, owner_user_id = _get_runtime_dependencies(runtime)

  if not memo_service or not owner_user_id:
    return Command(update={"messages": [_build_tool_message(runtime, "오류: 서비스 또는 사용자 정보를 찾을 수 없습니다.")]})

  memo_slots = _build_memo_slots(input_data)
  res = interrupt(
    HITLInterruptData(
      category=AgentResponseSSECategory.HITL,
      message="메모 추가 작업을 승인해주세요",
      intent=IntentType.MEMO,
      action=ActionType.ADD,
      memo_slots=memo_slots,
    )
  )

  user_confirmed, updated_slots = parse_memo_confirmation(res)
  if user_confirmed != HITLResultType.APPROVE:
    return Command(update={"messages": [_build_tool_message(runtime, REJECTED_BY_USER_MESSAGE)]})

  approved_memo = updated_slots or memo_slots
  payload = MemoCreate(
    title=approved_memo.title or input_data.title,
    content=approved_memo.content if approved_memo.content is not None else input_data.content,
  )

  try:
    result = await memo_service.create_memo(owner_user_id, payload)
    msg = f"새로운 메모가 추가되었습니다: ID={result.id}, 제목='{result.title}'"
    logger.info(msg)
  except Exception as e:
    msg = f"추가 실패: {e!s}"
    logger.error(msg)

  return Command(update={"messages": [_build_tool_message(runtime, msg)]})
