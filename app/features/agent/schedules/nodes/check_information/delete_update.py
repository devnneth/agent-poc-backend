import logging

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from app.features.agent.entity import ActionType
from app.features.agent.entity import AgentNodeName as Nodes
from app.features.agent.entity import ScheduleExtractedInfo
from app.features.agent.state import RootState
from app.infrastructure.models.google_calendar_event_model import GoogleCalendarEventModel

from .common import interrupt_and_resume

logger = logging.getLogger(__name__)


async def check_delete_update(
  state: RootState,
  config: RunnableConfig,
  action: ActionType,
  schedule_slots: ScheduleExtractedInfo,
  schedule_list_raw: list,
) -> Command:
  """DELETE/UPDATE 액션의 대상 매칭 및 정보 충분성을 검증합니다."""
  # 대상이 지정되어 있으면, 후보군에 진짜 대상이 있는지 확인한다.
  schedule_slots = _match_target_from_list(action, schedule_slots, schedule_list_raw)

  # 대상이 없는 수정/삭제는 맥락에 맞는 안내 메시지로 추가 정보를 요청
  if not schedule_slots.schedule_id:
    action_label = "삭제" if action == ActionType.DELETE else "수정"
    missing_message = (
      f"검색된 일정 목록에서 {action_label}할 일정의 번호를 선택해주세요."
      if schedule_list_raw
      else f"{action_label}할 일정을 먼저 검색해주세요. 일정 제목이나 날짜를 알려주시면 찾아드릴게요."
    )
    return await interrupt_and_resume(state, config, action, schedule_slots, missing_message)

  # 대상이 있는 수정/삭제는 정보가 충분하다고 간주 → 사용자 승인 요청
  return Command(goto=Nodes.USER_CONFIRM.value, update={"schedule_slots": schedule_slots})


def _match_target_from_list(action: ActionType, schedule_slots: ScheduleExtractedInfo, schedule_list_raw: list) -> ScheduleExtractedInfo:
  """수정/삭제 대상 schedule_id가 후보군에 실제로 존재하는지 확인하고 slots을 갱신합니다."""
  schedule_id = schedule_slots.schedule_id
  if not schedule_id:
    return schedule_slots

  # 타입 변환
  schedule_list: list[GoogleCalendarEventModel] = [
    GoogleCalendarEventModel.model_validate(item) if isinstance(item, dict) else item for item in schedule_list_raw
  ]

  # 후보군에서 매칭되는지 탐색
  matched = next((item for item in schedule_list if str(item.id) == str(schedule_id)), None)

  # 매칭되면 대상 정보를 설정한다.
  if matched:
    logger.info("⭐[check_information_node] target matched")
    matched_data = {
      "summary": matched.summary,
      "start_at": matched.start_at.isoformat() if matched.start_at else None,
      "end_at": matched.end_at.isoformat() if matched.end_at else None,
      "description": matched.description,
    }

    # 수정: 추출된 변경 정보를 우선하고, 없는 필드만 기존 값으로 채움
    if action == ActionType.UPDATE:
      matched_data = {k: getattr(schedule_slots, k) or v for k, v in matched_data.items()}

    return schedule_slots.model_copy(update=matched_data)

  # 없으면 schedule_id를 비운다
  return schedule_slots.model_copy(update={"schedule_id": None})
