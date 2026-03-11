import logging
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import cast

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from app.features.agent.entity import ActionType
from app.features.agent.entity import AgentNodeName as Nodes
from app.features.agent.entity import ScheduleExtractedInfo
from app.features.agent.helpers.graph_helpers import apply_nostream
from app.features.agent.helpers.graph_helpers import fill_end_at
from app.features.agent.helpers.graph_helpers import get_llm
from app.features.agent.helpers.prompt import load_prompt
from app.features.agent.settings import AGENT_MODEL_SETTINGS as AMS
from app.features.agent.state import RootState

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

logger = logging.getLogger(__name__)


async def extract_information_node(state: RootState, config: RunnableConfig) -> Command:
  """결정된 액션에 필요한 세부 파라미터(슬롯)를 추출합니다."""
  # 정보 추출
  action = state.get("action")
  schedule_slots = state.get("schedule_slots") or ScheduleExtractedInfo()
  minutes_offset = config.get("configurable", {}).get("minutes_offset", 540)
  current_time = datetime.now(UTC) + timedelta(minutes=minutes_offset)
  schedule_list = state.get("schedule_list") or []

  # 액션별 프롬프트 선택
  if action is None:
    prompt_file = "extract_info.txt"
  elif action == ActionType.ADD:
    prompt_file = "extract_info_add.txt"
  elif action in [ActionType.DELETE, ActionType.UPDATE]:
    prompt_file = "extract_info_del_udt.txt"
  elif action == ActionType.SEARCH:
    prompt_file = "extract_info_search.txt"
  else:
    prompt_file = "extract_info.txt"

  # 시스템 프롬프트
  sys_msg = SystemMessage(
    content=load_prompt(PROMPTS_DIR / prompt_file).format(
      current_time=current_time.strftime("%Y-%m-%d %H:%M:%S (%A)"),
      existing_slots=schedule_slots.model_dump(),
      action=action,
      search_result=schedule_list,
    )
  )

  # LLM 엔진 호출
  current_node = Nodes.EXTRACT_INFO.value
  structured_llm = get_llm(current_node, config).with_structured_output(ScheduleExtractedInfo)
  chain = apply_nostream(structured_llm, AMS[current_node])

  # 실행
  response = cast(ScheduleExtractedInfo, await chain.ainvoke([sys_msg, *state.get("messages", [])], config=config))

  # 갱신
  schedule_slots = schedule_slots.model_copy(update={k: v for k, v in response.model_dump().items() if v is not None})
  schedule_slots = fill_end_at(schedule_slots)

  logger.info(f"⭐[extract_information_node] 정보추출완료. action: {action}")
  logger.info(f"⭐[extract_information_node] Extracted: {schedule_slots.model_dump(exclude_none=True)}")

  return Command(goto=Nodes.CHECK_INFO.value, update={"schedule_slots": schedule_slots})
