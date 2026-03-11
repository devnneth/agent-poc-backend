import logging
from typing import Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command
from langgraph.types import interrupt
from pydantic import BaseModel
from pydantic import Field

from app.api.common.request_entity import TodoPriority
from app.api.common.request_entity import TodoStatus
from app.api.common.response_entity import AgentResponseSSECategory
from app.features.agent.entity import ActionType
from app.features.agent.entity import HITLInterruptData
from app.features.agent.entity import HITLResultType
from app.features.agent.entity import IntentType
from app.features.agent.entity import TodoExtractedInfo
from app.features.agent.entity import build_hitl_interrupt_payload
from app.features.agent.helpers.graph_helpers import parse_todo_confirmation
from app.features.agent.state import RootState
from app.features.agent.todo.prompts.tools.common import REJECTED_BY_USER_MESSAGE
from app.features.agent.todo.prompts.tools.update import DESCRIPTION
from app.features.agent.todo.tools.todo.utils import find_todo_in_state
from app.features.todos.todo_dto import TodoUpdate
from app.infrastructure.models.todo_model import TodoModel

logger = logging.getLogger(__name__)


class UpdateTodoInput(BaseModel):
  todo_id: int = Field(description="수정할 할일의 고유 ID")
  title: str | None = Field(default=None, description="새로운 제목 (수정할 경우에만 입력)")
  description: str | None = Field(default=None, description="새로운 상세 설명")
  status: TodoStatus | None = Field(default=None, description="새로운 상태")
  priority: TodoPriority | None = Field(default=None, description="새로운 우선순위")
  project: str | None = Field(default=None, description="새로운 프로젝트/카테고리")


def _build_tool_message(runtime: ToolRuntime[Any, RootState], content: str) -> ToolMessage:
  """현재 tool call에 연결된 응답 메시지를 생성합니다."""
  return ToolMessage(content=content, tool_call_id=runtime.tool_call_id)


def _get_runtime_dependencies(runtime: ToolRuntime[Any, RootState]) -> tuple[Any, str | None]:
  """ToolRuntime에서 update_todo_tool 실행에 필요한 의존성을 추출합니다."""
  configurable = runtime.config.get("configurable") or {}
  todo_service = configurable.get("todo_service")
  owner_user_id = configurable.get("user_id")
  return todo_service, owner_user_id


def _build_merged_todo_slots(current_todo: TodoModel, input_data: UpdateTodoInput) -> TodoExtractedInfo:
  """현재 저장된 값과 사용자의 수정 요청을 합쳐 HITL에 전달할 데이터를 구성합니다."""
  current_slots = TodoExtractedInfo(
    todo_id=current_todo.id,
    title=current_todo.title,
    description=current_todo.description,
    status=current_todo.status,
    priority=current_todo.priority,
    project=current_todo.project,
  )
  requested_changes = input_data.model_dump(exclude={"todo_id"}, exclude_none=True)
  return current_slots.model_copy(update=requested_changes)


def _build_update_payload(current_todo: TodoModel, approved_todo: TodoExtractedInfo) -> TodoUpdate:
  """승인된 할일 정보와 현재 값을 비교해 실제 변경 필드만 추출합니다."""
  changed_fields: dict[str, str] = {}
  for field_name in ["title", "description", "status", "priority", "project"]:
    approved_value = getattr(approved_todo, field_name)
    current_value = getattr(current_todo, field_name)
    if approved_value is not None and approved_value != current_value:
      changed_fields[field_name] = approved_value
  return TodoUpdate.model_validate(changed_fields)


def _build_updated_todo_list(state: RootState, todo_id: int, updated_todo: TodoModel) -> list[TodoModel] | None:
  """수정 성공 후 RootState의 todo_list에서 대상 항목만 최신 값으로 교체합니다."""
  current_todo_list = state.get("todo_list") or []
  if not current_todo_list:
    return None

  new_todo_list: list[TodoModel] = []
  for todo in current_todo_list:
    current_id = todo.get("id") if isinstance(todo, dict) else getattr(todo, "id", None)
    if current_id == todo_id:
      new_todo_list.append(updated_todo)
    else:
      new_todo_list.append(TodoModel.model_validate(todo) if isinstance(todo, dict) else todo)
  return new_todo_list


@tool(description=DESCRIPTION)
async def update_todo_tool(input_data: UpdateTodoInput, runtime: ToolRuntime[Any, RootState]) -> Command:
  """기존 할일을 수정합니다. 수정 전에는 반드시 HITL 승인을 받습니다."""
  logger.info(f"Updating todo ID={input_data.todo_id}: {input_data}")
  todo_service, owner_user_id = _get_runtime_dependencies(runtime)
  state = runtime.state

  if not todo_service or not owner_user_id:
    return Command(update={"messages": [_build_tool_message(runtime, "오류: 서비스 또는 사용자 정보를 찾을 수 없습니다.")]})

  current_todo = find_todo_in_state(state, input_data.todo_id)
  if not current_todo:
    msg = "수정할 할일을 먼저 검색해주세요. 검색 결과에서 할일 ID를 확인한 뒤 다시 요청해주세요."
    logger.error(msg)
    return Command(update={"messages": [_build_tool_message(runtime, msg)]})

  logger.info(f"current_todo: {current_todo}")

  todo_slots = _build_merged_todo_slots(current_todo, input_data)
  logger.info(f"todo_slots: {todo_slots}")

  res = interrupt(
    build_hitl_interrupt_payload(
      HITLInterruptData(
        category=AgentResponseSSECategory.HITL,
        message="할일 수정 작업을 승인해주세요",
        intent=IntentType.TODO,
        action=ActionType.UPDATE,
        todo_slots=todo_slots,
      )
    )
  )

  user_confirmed, updated_slots = parse_todo_confirmation(res)
  logger.info(f"user_confirmed: {user_confirmed}")
  logger.info(f"updated_slots: {updated_slots}")

  if user_confirmed != HITLResultType.APPROVE:
    return Command(update={"messages": [_build_tool_message(runtime, REJECTED_BY_USER_MESSAGE)]})

  approved_todo = updated_slots or todo_slots
  payload = _build_update_payload(current_todo, approved_todo)

  try:
    updated_model = await todo_service.update_todo(owner_user_id, input_data.todo_id, payload)
    todo_list = _build_updated_todo_list(state, input_data.todo_id, updated_model)
    msg = f"할일(ID={input_data.todo_id}) 정보가 수정되었습니다."
    logger.info(msg)
    return Command(update={"todo_list": todo_list, "messages": [_build_tool_message(runtime, msg)]})
  except ValueError as e:
    msg = f"수정 실패: {e!s}"
    logger.error(msg)
    return Command(update={"messages": [_build_tool_message(runtime, msg)]})
