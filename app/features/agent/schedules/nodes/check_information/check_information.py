import logging
from typing import cast

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from app.features.agent.entity import ActionType
from app.features.agent.entity import ScheduleExtractedInfo
from app.features.agent.state import RootState

from .add import check_add
from .delete_update import check_delete_update
from .search import check_search

logger = logging.getLogger(__name__)


async def check_information_node(state: RootState, config: RunnableConfig) -> Command:
  """결정된 액션에 필요한 세부 파라미터(슬롯)가 충분한지 검토합니다."""

  action = state.get("action")
  schedule_slots = state.get("schedule_slots") or ScheduleExtractedInfo()
  schedule_list_raw = state.get("schedule_list") or []

  logger.info(f"⭐[check_information_node] 정보검증노드. action: {action}")

  # 삭제 / 수정
  if action in (ActionType.DELETE, ActionType.UPDATE):
    return await check_delete_update(state, config, cast(ActionType, action), schedule_slots, schedule_list_raw)

  # 검색
  if action == ActionType.SEARCH:
    return await check_search(state, config, cast(ActionType, action), schedule_slots)

  # 추가
  return await check_add(state, config, action, schedule_slots)
