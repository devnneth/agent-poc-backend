import logging
from pathlib import Path
from typing import cast

from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from pydantic import BaseModel
from pydantic import Field

from app.features.agent.entity import AgentNodeName as Nodes
from app.features.agent.entity import RouterIntent
from app.features.agent.helpers.graph_helpers import apply_nostream
from app.features.agent.helpers.graph_helpers import get_llm
from app.features.agent.helpers.prompt import load_prompt
from app.features.agent.settings import AGENT_MODEL_SETTINGS as AMS
from app.features.agent.state import RootState

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

logger = logging.getLogger(__name__)

TODO_KEYWORDS = ("할일", "할 일", "todo", "투두")
MEMO_KEYWORDS = ("메모", "memo", "노트", "기록")
SCHEDULE_KEYWORDS = ("일정", "스케줄", "calendar", "캘린더")


# OpenAI structured output을 위한 Pydantic 모델, RouterIntent는 Enum 타입이므로 래핑 필요
class RootIntentResult(BaseModel):
  """루트 라우터의 구조화 의도 분류 결과"""

  intent: RouterIntent = Field(description="루트 라우터가 선택한 다음 노드 이름")


def _extract_last_user_message(state: RootState) -> str:
  """마지막 사용자 발화를 추출합니다."""
  for message in reversed(state.get("messages", [])):
    if isinstance(message, HumanMessage):
      return str(message.content).strip()
  return ""


def _contains_any_keyword(message: str, keywords: tuple[str, ...]) -> bool:
  """문장 안에 지정 키워드가 하나라도 포함되는지 확인합니다."""
  normalized = message.casefold()
  return any(keyword.casefold() in normalized for keyword in keywords)


def _route_explicit_domain_request(last_user_message: str) -> RouterIntent | None:
  """명시적인 도메인 요청은 LLM 호출 전에 규칙 기반으로 우선 라우팅합니다."""
  if not last_user_message:
    return None

  if _contains_any_keyword(last_user_message, MEMO_KEYWORDS):
    return RouterIntent.MEMO_AGENT

  if _contains_any_keyword(last_user_message, TODO_KEYWORDS):
    return RouterIntent.TODO_AGENT

  if _contains_any_keyword(last_user_message, SCHEDULE_KEYWORDS):
    return RouterIntent.SCHEDULE_AGENT

  return None


async def root_intent_node(state: RootState, config: RunnableConfig):
  """사용자 메시지의 의도를 분류합니다."""
  last_user_message = _extract_last_user_message(state)
  explicit_route = _route_explicit_domain_request(last_user_message)
  if explicit_route is not None:
    logger.info("⭐[root_intent_node] explicit_route: %s", explicit_route)
    return Command(goto=explicit_route)

  base_prompt = load_prompt(PROMPTS_DIR / "analyze_intent.txt")

  action = state.get("action")
  if action:
    hint = load_prompt(PROMPTS_DIR / "intent_context_hint.txt").format(action=action)
    full_prompt = base_prompt + "\n" + hint
  else:
    full_prompt = base_prompt

  system_msg = SystemMessage(content=full_prompt)

  current_node = Nodes.ROOT_INTENT.value
  structured_llm = get_llm(current_node, config).with_structured_output(RootIntentResult, method="function_calling")
  chain = apply_nostream(structured_llm, AMS[current_node])

  # 이전 대화 맥락 포함
  recent_messages = [m for m in state.get("messages", []) if isinstance(m, (HumanMessage, AIMessage, ToolMessage))]
  response = cast(RootIntentResult, await chain.ainvoke([system_msg, *recent_messages], config=config))
  next_node_name = response.intent
  logger.info(f"⭐[root_intent_node] next_node_name: {next_node_name}")

  return Command(goto=next_node_name)
