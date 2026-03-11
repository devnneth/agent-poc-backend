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
from app.features.agent.helpers.graph_helpers import parse_user_confirmed
from app.features.agent.memo.prompts.tools.common import REJECTED_BY_USER_MESSAGE
from app.features.agent.memo.prompts.tools.delete import DESCRIPTION
from app.features.agent.memo.tools.memo.utils import find_memo_in_state
from app.features.agent.state import RootState
from app.infrastructure.models.memo_model import MemoModel

logger = logging.getLogger(__name__)


def _build_tool_message(runtime: ToolRuntime[Any, Any], content: str) -> ToolMessage:
  """현재 tool call에 연결된 응답 메시지를 생성합니다."""
  return ToolMessage(content=content, tool_call_id=runtime.tool_call_id)


def _build_memo_slots(memo: MemoModel) -> MemoExtractedInfo:
  """검색된 메모 정보를 HITL payload용 memo_slots로 변환합니다."""
  return MemoExtractedInfo(
    memo_id=memo.id,
    title=memo.title,
    content=memo.content,
  )


def _build_memo_list_without_target(state: RootState, memo_id: int) -> list[MemoModel] | None:
  """삭제 성공 후 RootState의 memo_list에서 대상 항목만 제거합니다."""
  current_memo_list = state.get("memo_list") or []
  new_memo_list: list[MemoModel] = []

  for memo in current_memo_list:
    current_id = memo.get("id") if isinstance(memo, dict) else getattr(memo, "id", None)
    if current_id != memo_id:
      new_memo_list.append(MemoModel.model_validate(memo) if isinstance(memo, dict) else memo)
  return new_memo_list


@tool(description=DESCRIPTION)
async def delete_memo_tool(memo_id: int, runtime: ToolRuntime[Any, RootState]) -> Command:
  """메모를 삭제합니다. 삭제 전에는 검색과 HITL 승인을 거칩니다."""
  configurable = runtime.config.get("configurable") or {}
  memo_service = configurable.get("memo_service")
  owner_user_id = configurable.get("user_id")
  state = runtime.state
  logger.info("Deleting memo ID=%s", memo_id)

  if not memo_service or not owner_user_id:
    return Command(update={"messages": [_build_tool_message(runtime, "오류: 서비스 또는 사용자 정보를 찾을 수 없습니다.")]})

  current_memo = find_memo_in_state(state, memo_id)
  if not current_memo:
    msg = "삭제할 메모를 먼저 검색해주세요. 검색 결과에서 메모 ID를 확인한 뒤 다시 요청해주세요."
    logger.error(msg)
    return Command(update={"messages": [_build_tool_message(runtime, msg)]})

  res = interrupt(
    HITLInterruptData(
      category=AgentResponseSSECategory.HITL,
      message="메모 삭제 작업을 승인해주세요",
      intent=IntentType.MEMO,
      action=ActionType.DELETE,
      memo_slots=_build_memo_slots(current_memo),
    )
  )

  user_confirmed = parse_user_confirmed(res)
  if user_confirmed != HITLResultType.APPROVE:
    return Command(update={"messages": [_build_tool_message(runtime, REJECTED_BY_USER_MESSAGE)]})

  try:
    memo_service.delete_memo(owner_user_id, memo_id)
    memo_list = _build_memo_list_without_target(state, memo_id)
    msg = f"메모(ID={memo_id}) 정보가 삭제되었습니다."
    logger.info(msg)
    return Command(update={"memo_list": memo_list, "messages": [_build_tool_message(runtime, msg)]})
  except ValueError as e:
    msg = f"삭제 실패: {e!s}"
    logger.error(msg)
    return Command(update={"messages": [_build_tool_message(runtime, msg)]})
