import logging
from pathlib import Path

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from langgraph.types import interrupt

from app.api.common.response_entity import AgentResponseSSECategory
from app.features.agent.entity import AgentNodeName as Nodes
from app.features.agent.entity import HITLInterruptData
from app.features.agent.entity import HITLResultType
from app.features.agent.entity import IntentType
from app.features.agent.entity import ScheduleExtractedInfo
from app.features.agent.helpers.graph_helpers import parse_schedule_confirmation
from app.features.agent.state import RootState

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

logger = logging.getLogger(__name__)


async def user_confirmation_node(state: RootState, config: RunnableConfig) -> Command:
  """필수 정보가 모두 수집된 상태에서 사용자에게 최종 승인을 요청하는 메시지를 작성합니다."""
  action = state.get("action")
  schedule_slots = state.get("schedule_slots") or ScheduleExtractedInfo()
  user_confirmed = state.get("user_confirmed")

  logger.info(f"⭐[user_confirmation_node] 사용자 확인 필요. action: {action}")
  logger.info(f"⭐[user_confirmation_node] schedule_slots: {schedule_slots}")

  # 사용자가 액션 수행을 승인한 경우, 도구 실행 노드로 이동
  if action and user_confirmed == HITLResultType.APPROVE:
    return Command(goto=Nodes.EXECUTE_TOOL.value)

  # 사용자가 액션 수행을 거절한 경우, 수행 취소 노드로 이동
  if action and user_confirmed == HITLResultType.REJECT:
    return Command(goto=Nodes.FINAL_RESPONSE.value)

  # action에 따른 텍스트 생성
  action_text = "일정 추가"
  if action == "update":
    action_text = "일정 수정"
  elif action == "delete":
    action_text = "일정 삭제"

  # 사용자 승인/거절 확인 요청
  res = interrupt(
    HITLInterruptData(
      category=AgentResponseSSECategory.HITL,
      message=f"{action_text} 작업을 승인해주세요",
      intent=IntentType.SCHEDULE,
      action=action,
      schedule_slots=schedule_slots.model_copy(update={"description": schedule_slots.description or ""}),  # 설명란이 비어있어도 포함
    ).model_dump(exclude_none=True)
  )

  # 사용자 입력(res)을 파싱하여 승인/거절 여부 및 수정된 슬롯 추출
  user_confirmed, updated_slots = parse_schedule_confirmation(res)
  update: dict = {"user_confirmed": user_confirmed}

  # 수정인경우, 내용 갱신 (schedule_id는 클라이언트 입력으로 왜곡되지 않도록 보존)
  if action == "update" and updated_slots:
    logger.info(f"⭐[user_confirmation_node] 사용자의 수정 응답: {res}")
    update["schedule_slots"] = updated_slots.model_copy(update={"schedule_id": schedule_slots.schedule_id})  # id는 원래것 사용

  # 승인 노드로 이동
  return Command(goto=Nodes.USER_CONFIRM.value, update=update)
