import logging
from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from app.core.config.environment import settings
from app.features.agent.entity import ActionType
from app.features.agent.entity import AgentNodeName as Nodes
from app.features.agent.entity import HITLResultType
from app.features.agent.entity import ScheduleExtractedInfo
from app.features.agent.schedules.tools.add import add_schedule
from app.features.agent.schedules.tools.delete import delete_schedule
from app.features.agent.schedules.tools.search import search_schedule
from app.features.agent.schedules.tools.update import update_schedule
from app.features.agent.state import RootState
from app.infrastructure.models.google_calendar_event_model import GoogleCalendarEventModel

logger = logging.getLogger(__name__)


async def execute_tool_node(state: RootState, config: RunnableConfig) -> Command:
  """승인이 완료된 요청에 대해 실제 툴(도구)을 호출합니다."""
  # 데이터 추출
  action = state.get("action")
  schedule_slots = state.get("schedule_slots") or ScheduleExtractedInfo()
  user_confirmed = state.get("user_confirmed")
  schedule_id = schedule_slots.schedule_id

  logger.info(f"⭐[execute_tool_node] 도구 실행노드. action: {action}")

  # 사용자 승인 확인
  if user_confirmed != HITLResultType.APPROVE and action != ActionType.SEARCH:
    return Command(goto=Nodes.FINAL_RESPONSE.value, update={"messages": [AIMessage(content="요청 취소")]})

  # 파라미터 가공
  schedule_slots = schedule_slots if isinstance(schedule_slots, ScheduleExtractedInfo) else ScheduleExtractedInfo()
  schedule_slots_dict = schedule_slots.model_dump(exclude_none=True)

  execution_success = True
  result_msg = ""
  schedule_list = []
  delete_result = None

  # 도구 실행
  try:
    match action:
      case ActionType.ADD:
        add_args = {k: v for k, v in schedule_slots_dict.items() if k in ["summary", "start_at", "end_at", "description", "color_id"]}
        result_msg = await add_schedule.ainvoke(add_args, config)

      case ActionType.UPDATE:
        update_args = {k: v for k, v in schedule_slots_dict.items() if k in ["schedule_id", "summary", "start_at", "end_at", "description", "color_id"]}
        result_msg = await update_schedule.ainvoke(update_args, config)

      case ActionType.DELETE:
        delete_result = str(await delete_schedule.ainvoke({"schedule_id": schedule_id}, config))
        result_msg = ""

      case ActionType.SEARCH:
        search_args = {k: v for k, v in schedule_slots_dict.items() if k in ["query", "start_at", "end_at"]}
        search_args["max_results"] = settings.SEARCH_MAX_RESULTS
        schedule_list = await search_schedule.ainvoke(search_args, config)
        result_msg = ""

      case _:
        result_msg = f"오류 : 알 수 없는 액션입니다: {action}"
        execution_success = False

  except Exception as e:
    result_msg = f"오류 : 도구 실행 중 문제가 발생했습니다: {e!s}"
    execution_success = False

  # 도구 실행 결과 메시지를 확인하여 실패 여부 판단 (논리적 실패 대응)
  has_error_text = any(fail_word in result_msg for fail_word in ["실패", "오류", "error", "failed"]) if isinstance(result_msg, str) else False
  execution_success = False if has_error_text else execution_success

  # 회신 메시지 빌딩
  update_data: dict[str, Any] = {}

  if (
    action == ActionType.SEARCH
    and execution_success
    and isinstance(schedule_list, list)
    and all(isinstance(r, GoogleCalendarEventModel) for r in schedule_list)
  ):
    update_data = {
      "messages": [AIMessage(content=f"검색 완료: {len(schedule_list)}건 발견")],
      "schedule_list": [r.model_dump(mode="json") for r in schedule_list],
    }
  else:
    update_data = {"messages": [AIMessage(content=str(result_msg))]}

    if action == ActionType.DELETE:
      update_data["delete_result"] = delete_result

  # 회신
  return Command(goto=Nodes.FINAL_RESPONSE.value, update=update_data)
