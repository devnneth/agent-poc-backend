import json
import logging
from collections.abc import Sequence
from typing import Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command
from pydantic import BaseModel
from pydantic import Field

from app.features.agent.memo.prompts.tools.search import DESCRIPTION
from app.features.agent.state import RootState
from app.features.memos.memo_dto import MemoSearchFilter
from app.infrastructure.models.memo_model import MemoModel

logger = logging.getLogger(__name__)


class SearchMemoInput(BaseModel):
  keyword: str | None = Field(default=None, description="검색할 키워드")


def _build_tool_message(runtime: ToolRuntime[Any, RootState], content: str) -> ToolMessage:
  """현재 tool call에 연결된 응답 메시지를 생성합니다."""
  return ToolMessage(content=content, tool_call_id=runtime.tool_call_id)


def _build_search_filter(input_data: SearchMemoInput) -> MemoSearchFilter:
  """입력값을 MemoSearchFilter로 변환합니다."""
  return MemoSearchFilter(keyword=input_data.keyword)


def _format_memo_cell(value: Any) -> str:
  """마크다운 표 셀에 안전하게 들어갈 문자열로 변환합니다."""
  if value is None or value == "":
    return "(없음)"
  return str(value).replace("|", "\\|").replace("\n", "<br/>")


def _build_memo_markdown_table(memos: Sequence[dict[str, Any]]) -> str:
  """메모 목록을 사용자 응답용 마크다운 표로 변환합니다."""
  lines = [
    "| ID | 제목 | 내용 |",
    "| --- | --- | --- |",
  ]

  for memo in memos:
    lines.append(
      "| {id} | {title} | {content} |".format(
        id=_format_memo_cell(memo.get("id")),
        title=_format_memo_cell(memo.get("title")),
        content=_format_memo_cell(memo.get("content")),
      ),
    )

  return "\n".join(lines)


def _serialize_memos(memos: Sequence[MemoModel]) -> list[dict[str, Any]]:
  """Tool 응답과 상태 저장에 사용할 직렬화 가능한 메모 목록을 생성합니다."""
  results = [t.model_dump(exclude={"owner_user_id", "updated_at", "deleted_at", "embedding_id"}) for t in memos]

  for result in results:
    if result.get("created_at"):
      result["created_at"] = result["created_at"].isoformat()

  return results


@tool(description=DESCRIPTION)
async def search_memo_tool(input_data: SearchMemoInput, runtime: ToolRuntime[Any, RootState]) -> Command:
  """메모를 검색하거나 목록을 조회합니다."""
  configurable = runtime.config.get("configurable") or {}
  memo_service = configurable.get("memo_service")
  owner_user_id = configurable.get("user_id")
  logger.info("Searching memos with filter: %s", input_data)

  if not memo_service or not owner_user_id:
    msg = "오류: 서비스 또는 사용자 정보를 찾을 수 없습니다."
    logger.error("Service or user info missing in search_memo_tool. Service present: %s, User ID: %s", bool(memo_service), owner_user_id)
    return Command(update={"messages": [_build_tool_message(runtime, msg)]})

  memos: Sequence[MemoModel] = memo_service.read_memos(owner_user_id, _build_search_filter(input_data))
  logger.info("Read memos for user '%s': found %s items.", owner_user_id, len(memos))

  if not memos:
    logger.info("No memos found matching the criteria for user %s.", owner_user_id)
    return Command(update={"memo_list": [], "messages": [_build_tool_message(runtime, "검색 결과가 없습니다.")]})

  results = _serialize_memos(memos)
  markdown_result = _build_memo_markdown_table(results)
  new_msg = _build_tool_message(runtime, content=json.dumps({"memos": results, "markdown_table": markdown_result}, ensure_ascii=False))
  return Command(update={"memo_list": list(memos), "messages": [new_msg]})
