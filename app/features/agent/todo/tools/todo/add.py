import logging
from typing import Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command
from langgraph.types import interrupt

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
from app.features.agent.todo.prompts.tools.add import DESCRIPTION
from app.features.agent.todo.prompts.tools.common import REJECTED_BY_USER_MESSAGE
from app.features.todos.todo_dto import TodoCreate
from app.features.todos.todo_service import TodoService

logger = logging.getLogger(__name__)


def _build_tool_message(runtime: ToolRuntime[Any, RootState], content: str) -> ToolMessage:
  """현재 tool call에 연결된 응답 메시지를 생성합니다."""
  return ToolMessage(content=content, tool_call_id=runtime.tool_call_id)


def _get_runtime_dependencies(runtime: ToolRuntime[Any, RootState]) -> tuple[TodoService | None, str | None]:
  """ToolRuntime에서 add_todo_tool 실행에 필요한 의존성을 추출합니다."""
  configurable = runtime.config.get("configurable") or {}
  todo_service = configurable.get("todo_service")
  owner_user_id = configurable.get("user_id")
  return todo_service, owner_user_id


def _build_todo_slots(input_data: TodoCreate) -> TodoExtractedInfo:
  """추가 승인 화면에서 바로 확인/수정할 수 있도록 입력값을 todo_slots로 변환합니다."""
  return TodoExtractedInfo(
    title=input_data.title,
    description=input_data.description,
    status=input_data.status,
    priority=input_data.priority,
    project=input_data.project,
  )


def _resolve_status(input_data: TodoCreate, approved_todo: TodoExtractedInfo) -> TodoStatus:
  """승인 화면에서 수정된 상태가 있으면 enum으로 변환하고, 없으면 기존 입력값을 유지합니다."""
  if approved_todo.status is None:
    return input_data.status
  return TodoStatus(approved_todo.status)


def _resolve_priority(input_data: TodoCreate, approved_todo: TodoExtractedInfo) -> TodoPriority:
  """승인 화면에서 수정된 우선순위가 있으면 enum으로 변환하고, 없으면 기존 입력값을 유지합니다."""
  if approved_todo.priority is None:
    return input_data.priority
  return TodoPriority(approved_todo.priority)


@tool(description=DESCRIPTION)
async def add_todo_tool(input_data: TodoCreate, runtime: ToolRuntime[None, RootState]) -> Command:
  """새로운 할일을 추가합니다. 추가 전에는 반드시 HITL 승인을 받습니다."""
  logger.info(f"Adding new todo: title={input_data.title}, project={input_data.project}")
  todo_service, owner_user_id = _get_runtime_dependencies(runtime)

  if not todo_service or not owner_user_id:
    return Command(update={"messages": [_build_tool_message(runtime, "오류: 서비스 또는 사용자 정보를 찾을 수 없습니다.")]})

  todo_slots = _build_todo_slots(input_data)
  res = interrupt(
    build_hitl_interrupt_payload(
      HITLInterruptData(
        category=AgentResponseSSECategory.HITL,
        message="할일 추가 작업을 승인해주세요",
        intent=IntentType.TODO,
        action=ActionType.ADD,
        todo_slots=todo_slots,
      )
    )
  )

  user_confirmed, updated_slots = parse_todo_confirmation(res)
  if user_confirmed != HITLResultType.APPROVE:
    return Command(update={"messages": [_build_tool_message(runtime, REJECTED_BY_USER_MESSAGE)]})

  approved_todo = updated_slots or todo_slots
  payload = TodoCreate(
    title=approved_todo.title or input_data.title,
    description=approved_todo.description if approved_todo.description is not None else input_data.description,
    status=_resolve_status(input_data, approved_todo),
    priority=_resolve_priority(input_data, approved_todo),
    project=approved_todo.project if approved_todo.project is not None else input_data.project,
    due_date=input_data.due_date,
    sort_order=input_data.sort_order,
  )

  try:
    result = await todo_service.create_todo(owner_user_id, payload)
    msg = f"새로운 할일이 추가되었습니다: ID={result.id}, 제목='{result.title}'"
    logger.info(msg)
  except Exception as e:
    msg = f"추가 실패: {e!s}"
    logger.error(msg)

  return Command(update={"messages": [_build_tool_message(runtime, msg)]})
