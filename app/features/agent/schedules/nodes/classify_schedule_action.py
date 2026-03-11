import logging
from collections.abc import Sequence
from pathlib import Path

from langchain_core.messages import BaseMessage
from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from app.features.agent.entity import ActionType
from app.features.agent.entity import AgentNodeName as Nodes
from app.features.agent.helpers.graph_helpers import apply_nostream
from app.features.agent.helpers.graph_helpers import extract_enum_from_response
from app.features.agent.helpers.graph_helpers import get_llm
from app.features.agent.helpers.prompt import load_prompt
from app.features.agent.settings import AGENT_MODEL_SETTINGS as AMS
from app.features.agent.state import RootState

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

logger = logging.getLogger(__name__)


_ACTION_KEYWORDS: dict[ActionType, list[str]] = {
  ActionType.ADD: ["추가", "등록", "만들", "생성", "넣어"],
  ActionType.UPDATE: ["수정", "변경", "옮겨", "바꿔"],
  ActionType.DELETE: ["삭제", "지워", "취소", "없애"],
  ActionType.SEARCH: ["조회", "검색", "보여", "알려", "찾아", "확인"],
}


def _extract_action_from_latest_user_message(messages: Sequence[BaseMessage]) -> ActionType | None:
  """마지막 사용자 발화에서 명시적인 일정 액션 키워드를 우선 해석합니다."""
  latest_user_message = next((message for message in reversed(messages) if isinstance(message, HumanMessage)), None)
  if latest_user_message is None:
    return None

  content = str(latest_user_message.content).strip().lower()
  if not content:
    return None

  # 안내 문구가 섞인 다중 턴에서도 마지막 사용자 발화의 직접 명령을 우선 처리합니다.
  for action_type, keywords in _ACTION_KEYWORDS.items():
    if any(keyword in content for keyword in keywords):
      return action_type

  return None


async def classify_schedule_action_node(state: RootState, config: RunnableConfig) -> Command:
  """현재 대화 맥락에서 사용자가 원하는 일정 액션을 분류합니다."""
  action = state.get("action")
  messages = state.get("messages", [])

  explicit_action = _extract_action_from_latest_user_message(messages)
  if explicit_action is not None:
    return Command(goto=Nodes.EXTRACT_INFO.value, update={"action": explicit_action})

  # 시스템 프롬프트
  sys_msg = SystemMessage(content=load_prompt(PROMPTS_DIR / "classify_action.txt").format(existing_action=action))

  # LLM 엔진 호출
  current_node = Nodes.CLASSIFY_ACTION.value
  chain = apply_nostream(get_llm(current_node, config), AMS[current_node])

  # 실행
  response = await chain.ainvoke([sys_msg, *messages], config=config)

  # 분류
  action = extract_enum_from_response(ActionType, response)

  return Command(goto=Nodes.EXTRACT_INFO.value, update={"action": action})
