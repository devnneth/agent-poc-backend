from pathlib import Path
from typing import cast

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from app.features.agent.entity import ActionType
from app.features.agent.entity import AgentNodeName as Nodes
from app.features.agent.entity import ScheduleExtractedInfo
from app.features.agent.entity import SlotCheckResult
from app.features.agent.helpers.graph_helpers import apply_nostream
from app.features.agent.helpers.graph_helpers import get_llm
from app.features.agent.helpers.prompt import load_prompt
from app.features.agent.settings import AGENT_MODEL_SETTINGS as AMS
from app.features.agent.state import RootState

from .common import interrupt_and_resume

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


async def check_add(
  state: RootState,
  config: RunnableConfig,
  action: ActionType | None,
  schedule_slots: ScheduleExtractedInfo,
) -> Command:
  """ADD/기타 액션의 정보 충분성을 LLM으로 검증합니다."""
  current_node = Nodes.CHECK_INFO.value

  # 액션별 프롬프트 선택
  prompt_file = "check_info_add.txt" if action == ActionType.ADD else "check_info.txt"

  # 시스템 프롬프트
  sys_msg = SystemMessage(
    content=load_prompt(PROMPTS_DIR / prompt_file).format(
      action=action,
      slots_json=schedule_slots.model_dump_json(),
    )
  )

  # LLM 엔진 (Structured Output)
  structured_llm = get_llm(current_node, config).with_structured_output(SlotCheckResult)
  chain = apply_nostream(structured_llm, AMS[current_node])

  # 실행
  messages = state.get("messages", [])
  result = cast(SlotCheckResult, await chain.ainvoke([sys_msg, *messages], config=config))

  # 추출된 정보가 불충분한 경우
  if not result.is_sufficient:
    return await interrupt_and_resume(state, config, action, schedule_slots, result.missing_message or "")

  # 충분하면 사용자 승인요청 송신
  return Command(goto=Nodes.USER_CONFIRM.value, update={"schedule_slots": schedule_slots})
