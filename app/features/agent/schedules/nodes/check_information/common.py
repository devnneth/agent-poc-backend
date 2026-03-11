import logging
from pathlib import Path
from typing import cast

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from langgraph.types import interrupt

from app.api.common.response_entity import AgentResponseSSECategory
from app.features.agent.entity import ActionType
from app.features.agent.entity import AgentNodeName as Nodes
from app.features.agent.entity import HITLInterruptData
from app.features.agent.entity import IntentShiftResult
from app.features.agent.entity import IntentType
from app.features.agent.entity import ScheduleExtractedInfo
from app.features.agent.helpers.graph_helpers import apply_nostream
from app.features.agent.helpers.graph_helpers import get_llm
from app.features.agent.helpers.prompt import load_prompt
from app.features.agent.settings import AGENT_MODEL_SETTINGS as AMS
from app.features.agent.state import RootState

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"

logger = logging.getLogger(__name__)


async def interrupt_and_resume(
  state: RootState,
  config: RunnableConfig,
  action: ActionType | None,
  schedule_slots: ScheduleExtractedInfo,
  missing_message: str,
) -> Command:
  """정보 부족 시 interrupt로 사용자에게 추가 정보를 요청하고, resume 후 라우팅합니다."""
  # 사용자에게 추가 정보를 요구하는 메시지 전송 → interrupt 후 resume 데이터 수신
  resume_data = interrupt(
    HITLInterruptData(
      category=AgentResponseSSECategory.MESSAGE,
      message=missing_message,
      intent=IntentType.SCHEDULE,
      action=action,
      schedule_slots=schedule_slots,
    ).model_dump(exclude_none=True)
  )

  # resume 데이터에서 사용자 메시지 추출
  resume_messages = resume_data.get("messages", []) if isinstance(resume_data, dict) else []
  all_messages = list(state.get("messages", [])) + resume_messages

  # 재개 후 의도 전환 여부 감지 (resume 메시지 포함)
  is_shifted = await _detect_intent_shift(all_messages, config, action, schedule_slots, missing_message)
  if is_shifted:
    return Command(goto=Nodes.INTENT_SHIFT.value, update={"messages": resume_messages})

  # 추가정보를 받으면 분류부터 재실행 (resume 메시지를 state에 반영)
  return Command(goto=Nodes.CLASSIFY_ACTION.value, update={"messages": resume_messages})


async def _detect_intent_shift(
  messages: list,
  config: RunnableConfig,
  action: ActionType | None,
  schedule_slots: ScheduleExtractedInfo,
  missing_message: str,
) -> bool:
  """interrupt 재개 후 사용자의 응답이 의도 전환인지 판별합니다."""
  current_node = Nodes.INTENT_SHIFT.value

  sys_msg = SystemMessage(
    content=load_prompt(PROMPTS_DIR / "detect_intent_shift.txt").format(
      action=action,
      slots_json=schedule_slots.model_dump_json(),
      missing_message=missing_message,
    )
  )

  structured_llm = get_llm(current_node, config).with_structured_output(IntentShiftResult)
  chain = apply_nostream(structured_llm, AMS[current_node])

  result = cast(IntentShiftResult, await chain.ainvoke([sys_msg, *messages], config=config))
  logger.info(f"⭐[_detect_intent_shift] is_shifted: {result.is_shifted}")
  return result.is_shifted
