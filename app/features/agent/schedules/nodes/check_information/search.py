from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from app.features.agent.entity import ActionType
from app.features.agent.entity import AgentNodeName as Nodes
from app.features.agent.entity import HITLResultType
from app.features.agent.entity import ScheduleExtractedInfo
from app.features.agent.state import RootState

from .common import interrupt_and_resume


async def check_search(
  state: RootState,
  config: RunnableConfig,
  action: ActionType,
  schedule_slots: ScheduleExtractedInfo,
) -> Command:
  """SEARCH 액션의 정보 충분성을 검증합니다. start_at/end_at/query 중 하나라도 있으면 충분 — LLM 없이 코드로 판단"""
  has_info = schedule_slots.start_at or schedule_slots.end_at or schedule_slots.query
  if not has_info:
    return await interrupt_and_resume(
      state,
      config,
      action,
      schedule_slots,
      "어떤 일정을 찾고 계신가요? 조회할 기간이나 일정 제목을 알려주세요.",
    )

  # 정보가 충분한 검색 액션: 승인 없이 즉시 실행
  return Command(
    goto=Nodes.EXECUTE_TOOL.value,
    update={"user_confirmed": HITLResultType.APPROVE, "schedule_slots": schedule_slots},
  )
