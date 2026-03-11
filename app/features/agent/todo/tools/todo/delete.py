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
from app.features.agent.entity import TodoExtractedInfo
from app.features.agent.helpers.graph_helpers import parse_user_confirmed
from app.features.agent.state import RootState
from app.features.agent.todo.prompts.tools.common import REJECTED_BY_USER_MESSAGE
from app.features.agent.todo.prompts.tools.delete import DESCRIPTION
from app.features.agent.todo.tools.todo.utils import find_todo_in_state
from app.infrastructure.models.todo_model import TodoModel

logger = logging.getLogger(__name__)


def _build_tool_message(runtime: ToolRuntime[Any, Any], content: str) -> ToolMessage:
  """현재 tool call에 연결된 응답 메시지를 생성합니다."""
  return ToolMessage(content=content, tool_call_id=runtime.tool_call_id)


def _build_todo_slots(todo: TodoModel) -> TodoExtractedInfo:
  """검색된 할일 정보를 HITL payload용 todo_slots로 변환합니다."""
  return TodoExtractedInfo(
    todo_id=todo.id,
    title=todo.title,
    description=todo.description,
    status=todo.status,
    priority=todo.priority,
    project=todo.project,
  )


def _build_todo_list_without_target(state: RootState, todo_id: int) -> list[TodoModel] | None:
  """삭제 성공 후 RootState의 todo_list에서 대상 항목만 제거합니다."""
  current_todo_list = state.get("todo_list") or []
  new_todo_list: list[TodoModel] = []

  for todo in current_todo_list:
    current_id = todo.get("id") if isinstance(todo, dict) else getattr(todo, "id", None)
    if current_id != todo_id:
      new_todo_list.append(TodoModel.model_validate(todo) if isinstance(todo, dict) else todo)
  return new_todo_list


@tool(description=DESCRIPTION)
async def delete_todo_tool(todo_id: int, runtime: ToolRuntime[Any, RootState]) -> Command:
  """할일을 삭제합니다. 삭제 전에는 검색과 HITL 승인을 거칩니다."""
  configurable = runtime.config.get("configurable") or {}
  todo_service = configurable.get("todo_service")
  owner_user_id = configurable.get("user_id")
  state = runtime.state
  logger.info(f"Deleting todo ID={todo_id}")

  # 전제조건 검사
  if not todo_service or not owner_user_id:
    return Command(update={"messages": [_build_tool_message(runtime, "오류: 서비스 또는 사용자 정보를 찾을 수 없습니다.")]})

  # 검색 결과에서 대상 검사
  current_todo = find_todo_in_state(state, todo_id)
  if not current_todo:
    msg = "삭제할 할일을 먼저 검색해주세요. 검색 결과에서 할일 ID를 확인한 뒤 다시 요청해주세요."
    logger.error(msg)
    return Command(update={"messages": [_build_tool_message(runtime, msg)]})

  # 검색으로 확보한 현재 값을 todo_slots에 채워 클라이언트가 바로 확인/수정할 수 있게 합니다.
  todo_slots = _build_todo_slots(current_todo)
  res = interrupt(
    HITLInterruptData(
      category=AgentResponseSSECategory.HITL,
      message="할일 삭제 작업을 승인해주세요",
      intent=IntentType.TODO,
      action=ActionType.DELETE,
      todo_slots=todo_slots,
    )
  )

  # 응답 파싱
  user_confirmed = parse_user_confirmed(res)
  if user_confirmed != HITLResultType.APPROVE:
    return Command(update={"messages": [_build_tool_message(runtime, REJECTED_BY_USER_MESSAGE)]})

  # 삭제
  try:
    todo_service.delete_todo(owner_user_id, todo_id)
    todo_list = _build_todo_list_without_target(state, todo_id)
    msg = f"할일(ID={todo_id}) 정보가 삭제되었습니다."
    logger.info(msg)
    return Command(update={"todo_list": todo_list, "messages": [_build_tool_message(runtime, msg)]})

  except ValueError as e:
    msg = f"삭제 실패: {e!s}"
    logger.error(msg)
    return Command(update={"messages": [_build_tool_message(runtime, msg)]})
