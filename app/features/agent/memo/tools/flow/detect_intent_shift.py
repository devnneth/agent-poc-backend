import logging

from langchain_core.tools import tool
from langgraph.types import Command
from pydantic import BaseModel
from pydantic import Field

from app.features.agent.entity import AgentNodeName as Nodes
from app.features.agent.memo.prompts.tools.detect_intent_shift import DESCRIPTION

logger = logging.getLogger(__name__)


class IntentShiftInput(BaseModel):
  reason: str = Field(description="맥락에서 벗어났다고 판단한 이유 (사용자에게 설명할 때 사용될 수 있음)")


@tool(description=DESCRIPTION)
async def detect_intent_shift_tool(input_data: IntentShiftInput) -> Command:
  logger.info(f"⭐[detect_intent_shift_tool] 상위 라우터로 복귀 제어권을 넘깁니다. 사유: {input_data.reason}")

  return Command(
    goto=Nodes.ROOT_INTENT.value,
    graph=Command.PARENT,
  )
