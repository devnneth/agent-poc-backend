from datetime import datetime
from pathlib import Path

from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.types import Command

from app.features.agent.entity import AgentNodeName as Nodes
from app.features.agent.helpers.graph_helpers import apply_nostream
from app.features.agent.helpers.graph_helpers import get_llm
from app.features.agent.helpers.prompt import load_prompt
from app.features.agent.settings import AGENT_MODEL_SETTINGS as AMS
from app.features.agent.state import RootState

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

DOMAIN_KEYWORDS = ("메모", "memo", "노트", "기록", "할일", "할 일", "todo", "투두", "일정", "스케줄", "calendar", "캘린더")


def _extract_last_user_message(state: RootState) -> str:
  """마지막 사용자 발화를 추출합니다."""
  for message in reversed(state.get("messages", [])):
    if isinstance(message, HumanMessage):
      return str(message.content).strip()
  return ""


def _looks_like_domain_request(message: str) -> bool:
  """일반 대화 노드가 처리하면 안 되는 내부 데이터 요청인지 판별합니다."""
  normalized = message.casefold()
  return any(keyword.casefold() in normalized for keyword in DOMAIN_KEYWORDS)


async def general_conversation_node(state: RootState, config: RunnableConfig):
  """일상 대화를 처리합니다."""
  last_user_message = _extract_last_user_message(state)
  if _looks_like_domain_request(last_user_message):
    response = AIMessage(content="이 요청은 일반 대화로 처리할 수 없습니다. 메모, 할일, 일정 관련 요청은 다시 말씀해 주세요.")
    return Command(goto=END, update={"messages": [response]})

  system_msg = SystemMessage(
    content=load_prompt(PROMPTS_DIR / "general_conversation.txt").format(
      current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S (%A)"),
    )
  )

  current_node = Nodes.GENERAL_CONVERSATION.value
  chain = apply_nostream(get_llm(current_node, config), AMS[current_node])

  response = await chain.ainvoke([system_msg, *state.get("messages", [])], config=config)

  return Command(goto=END, update={"messages": [response]})
