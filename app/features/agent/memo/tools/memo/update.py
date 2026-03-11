import logging
from typing import Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command
from langgraph.types import interrupt
from pydantic import BaseModel
from pydantic import Field

from app.api.common.response_entity import AgentResponseSSECategory
from app.features.agent.entity import ActionType
from app.features.agent.entity import HITLInterruptData
from app.features.agent.entity import HITLResultType
from app.features.agent.entity import IntentType
from app.features.agent.entity import MemoExtractedInfo
from app.features.agent.helpers.graph_helpers import parse_memo_confirmation
from app.features.agent.memo.prompts.tools.common import REJECTED_BY_USER_MESSAGE
from app.features.agent.memo.prompts.tools.update import DESCRIPTION
from app.features.agent.memo.tools.memo.utils import find_memo_in_state
from app.features.agent.state import RootState
from app.features.memos.memo_dto import MemoUpdate
from app.infrastructure.models.memo_model import MemoModel

logger = logging.getLogger(__name__)


class UpdateMemoInput(BaseModel):
  memo_id: int = Field(description="수정할 메모의 고유 ID")
  title: str | None = Field(default=None, description="새로운 제목")
  content: str | None = Field(default=None, description="새로운 본문")


def _build_tool_message(runtime: ToolRuntime[Any, RootState], content: str) -> ToolMessage:
  """현재 tool call에 연결된 응답 메시지를 생성합니다."""
  return ToolMessage(content=content, tool_call_id=runtime.tool_call_id)


def _get_runtime_dependencies(runtime: ToolRuntime[Any, RootState]) -> tuple[Any, str | None]:
  """ToolRuntime에서 update_memo_tool 실행에 필요한 의존성을 추출합니다."""
  configurable = runtime.config.get("configurable") or {}
  memo_service = configurable.get("memo_service")
  owner_user_id = configurable.get("user_id")
  return memo_service, owner_user_id


def _build_merged_memo_slots(current_memo: MemoModel, input_data: UpdateMemoInput) -> MemoExtractedInfo:
  """현재 저장된 값과 사용자의 수정 요청을 합쳐 HITL에 전달할 데이터를 구성합니다."""
  current_slots = MemoExtractedInfo(
    memo_id=current_memo.id,
    title=current_memo.title,
    content=current_memo.content,
  )
  requested_changes = input_data.model_dump(exclude={"memo_id"}, exclude_none=True)
  return current_slots.model_copy(update=requested_changes)


def _build_update_payload(current_memo: MemoModel, approved_memo: MemoExtractedInfo) -> MemoUpdate:
  """승인된 메모 정보와 현재 값을 비교해 실제 변경 필드만 추출합니다."""
  changed_fields: dict[str, str] = {}
  for field_name in ["title", "content"]:
    approved_value = getattr(approved_memo, field_name)
    current_value = getattr(current_memo, field_name)
    if approved_value is not None and approved_value != current_value:
      changed_fields[field_name] = approved_value
  return MemoUpdate.model_validate(changed_fields)


def _build_updated_memo_list(state: RootState, memo_id: int, updated_memo: MemoModel) -> list[MemoModel] | None:
  """수정 성공 후 RootState의 memo_list에서 대상 항목만 최신 값으로 교체합니다."""
  current_memo_list = state.get("memo_list") or []
  if not current_memo_list:
    return None

  new_memo_list: list[MemoModel] = []
  for memo in current_memo_list:
    current_id = memo.get("id") if isinstance(memo, dict) else getattr(memo, "id", None)
    if current_id == memo_id:
      new_memo_list.append(updated_memo)
    else:
      new_memo_list.append(MemoModel.model_validate(memo) if isinstance(memo, dict) else memo)
  return new_memo_list


@tool(description=DESCRIPTION)
async def update_memo_tool(input_data: UpdateMemoInput, runtime: ToolRuntime[Any, RootState]) -> Command:
  """기존 메모를 수정합니다. 수정 전에는 반드시 HITL 승인을 받습니다."""
  logger.info("Updating memo ID=%s: %s", input_data.memo_id, input_data)
  memo_service, owner_user_id = _get_runtime_dependencies(runtime)
  state = runtime.state

  if not memo_service or not owner_user_id:
    return Command(update={"messages": [_build_tool_message(runtime, "오류: 서비스 또는 사용자 정보를 찾을 수 없습니다.")]})

  current_memo = find_memo_in_state(state, input_data.memo_id)
  if not current_memo:
    msg = "수정할 메모를 먼저 검색해주세요. 검색 결과에서 메모 ID를 확인한 뒤 다시 요청해주세요."
    logger.error(msg)
    return Command(update={"messages": [_build_tool_message(runtime, msg)]})

  memo_slots = _build_merged_memo_slots(current_memo, input_data)
  res = interrupt(
    HITLInterruptData(
      category=AgentResponseSSECategory.HITL,
      message="메모 수정 작업을 승인해주세요",
      intent=IntentType.MEMO,
      action=ActionType.UPDATE,
      memo_slots=memo_slots,
    )
  )

  user_confirmed, updated_slots = parse_memo_confirmation(res)
  if user_confirmed != HITLResultType.APPROVE:
    return Command(update={"messages": [_build_tool_message(runtime, REJECTED_BY_USER_MESSAGE)]})

  approved_memo = updated_slots or memo_slots
  payload = _build_update_payload(current_memo, approved_memo)

  try:
    updated_model = await memo_service.update_memo(owner_user_id, input_data.memo_id, payload)
    memo_list = _build_updated_memo_list(state, input_data.memo_id, updated_model)
    msg = f"메모(ID={input_data.memo_id}) 정보가 수정되었습니다."
    logger.info(msg)
    return Command(update={"memo_list": memo_list, "messages": [_build_tool_message(runtime, msg)]})
  except ValueError as e:
    msg = f"수정 실패: {e!s}"
    logger.error(msg)
    return Command(update={"messages": [_build_tool_message(runtime, msg)]})
