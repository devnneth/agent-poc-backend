import logging

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from app.features.agent.entity import AgentNodeName as Nodes
from app.features.agent.state import RootState

logger = logging.getLogger(__name__)


async def intent_shift_node(state: RootState, config: RunnableConfig) -> Command:
  """의도 전환 감지 시 현재 작업을 취소하고 새 의도를 처음부터 처리합니다."""
  logger.info("⭐[intent_shift_node] 의도 전환 감지")
  return Command(
    goto=Nodes.ROOT_INTENT.value,
    update={"action": None, "schedule_slots": {}, "user_confirmed": None},
    graph=Command.PARENT,
  )
