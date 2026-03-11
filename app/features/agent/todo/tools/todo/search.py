import json
import logging
from collections.abc import Sequence
from datetime import date
from typing import Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command
from pydantic import BaseModel
from pydantic import Field

from app.api.common.request_entity import TodoStatus
from app.features.agent.state import RootState
from app.features.agent.todo.prompts.tools.search import DESCRIPTION
from app.features.todos.todo_dto import TodoSearchFilter
from app.infrastructure.models.todo_model import TodoModel

logger = logging.getLogger(__name__)


class SearchTodoInput(BaseModel):
  keyword: str | None = Field(default=None, description="검색할 키워드")
  status: TodoStatus | None = Field(default=None, description="필터링할 상태")
  project: str | None = Field(default=None, description="필터링할 프로젝트")


def _build_tool_message(runtime: ToolRuntime[Any, RootState], content: str) -> ToolMessage:
  """현재 tool call에 연결된 응답 메시지를 생성합니다."""
  return ToolMessage(content=content, tool_call_id=runtime.tool_call_id)


def _build_search_filter(input_data: SearchTodoInput) -> TodoSearchFilter:
  """입력값을 TodoSearchFilter로 변환합니다."""
  limit = None
  if not input_data.keyword and not input_data.status and not input_data.project:
    logger.info("No search criteria provided. Fetching recent 5 todos.")
    limit = 5

  return TodoSearchFilter(
    keyword=input_data.keyword,
    status=input_data.status,
    project=input_data.project,
    limit=limit,
  )


def _format_todo_cell(value: Any) -> str:
  """마크다운 표 셀에 안전하게 들어갈 문자열로 변환합니다."""
  if value is None or value == "":
    return "(없음)"
  if isinstance(value, date):
    return value.isoformat()

  return str(value).replace("|", "\\|").replace("\n", "<br/>")


def _build_todo_markdown_table(todos: Sequence[dict[str, Any]]) -> str:
  """할일 목록을 사용자 응답용 마크다운 표로 변환합니다."""
  lines = [
    "| ID | 제목 | 상태 | 우선순위 | 설명 |",
    "| --- | --- | --- | --- | --- |",
  ]

  for todo in todos:
    lines.append(
      "| {id} | {title} | {status} | {priority} | {description} |".format(
        id=_format_todo_cell(todo.get("id")),
        title=_format_todo_cell(todo.get("title")),
        status=_format_todo_cell(todo.get("status")),
        priority=_format_todo_cell(todo.get("priority")),
        description=_format_todo_cell(todo.get("description")),
      ),
    )

  return "\n".join(lines)


def _serialize_todos(todos: Sequence[TodoModel]) -> list[dict[str, Any]]:
  """Tool 응답과 상태 저장에 사용할 직렬화 가능한 할일 목록을 생성합니다."""
  results = [t.model_dump(exclude={"owner_user_id", "updated_at", "deleted_at", "embedding_id", "sort_order"}) for t in todos]

  for result in results:
    if result.get("due_date"):
      result["due_date"] = str(result["due_date"])
    if result.get("created_at"):
      result["created_at"] = result["created_at"].isoformat()

  return results


@tool(description=DESCRIPTION)
async def search_todo_tool(input_data: SearchTodoInput, runtime: ToolRuntime[Any, RootState]) -> Command:
  """할일을 검색하거나 목록을 조회합니다."""
  configurable = runtime.config.get("configurable") or {}
  todo_service = configurable.get("todo_service")
  owner_user_id = configurable.get("user_id")
  logger.info(f"Searching todos with filter: {input_data}")

  # 검사
  if not todo_service or not owner_user_id:
    msg = "오류: 서비스 또는 사용자 정보를 찾을 수 없습니다."
    logger.error(f"Service or user info missing in search_todo_tool. Service present: {bool(todo_service)}, User ID: {owner_user_id}")
    return Command(update={"messages": [_build_tool_message(runtime, msg)]})

  # 검색
  filters = _build_search_filter(input_data)
  todos: Sequence[TodoModel] = todo_service.read_todos(owner_user_id, filters)
  logger.info(f"Read todos for user '{owner_user_id}': found {len(todos)} items.")

  # 결과가 없으면
  if not todos:
    logger.info(f"No todos found matching the criteria for user {owner_user_id}.")
    return Command(update={"todo_list": [], "messages": [_build_tool_message(runtime, "검색 결과가 없습니다.")]})

  # 결과 가공
  results = _serialize_todos(todos)
  markdown_result = _build_todo_markdown_table(results)
  new_msg = _build_tool_message(runtime, content=json.dumps({"todos": results, "markdown_table": markdown_result}, ensure_ascii=False))
  logger.info(f"Search found {len(results)} items.")

  # 결과 리턴
  return Command(update={"todo_list": list(todos), "messages": [new_msg]})
