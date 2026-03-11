import logging
from typing import Any

from langchain.agents import create_agent

from app.features.agent.memo.prompts.memo_prompt import SYSTEM_PROMPT
from app.features.agent.memo.tools.flow.detect_intent_shift import detect_intent_shift_tool
from app.features.agent.memo.tools.memo.add import add_memo_tool
from app.features.agent.memo.tools.memo.delete import delete_memo_tool
from app.features.agent.memo.tools.memo.search import search_memo_tool
from app.features.agent.memo.tools.memo.update import update_memo_tool
from app.features.agent.state import RootState
from app.features.llm.llm_service import LLMServiceFactory

logger = logging.getLogger(__name__)


def create_memo_agent_graph(checkpointer: Any = None):
  """메모 에이전트 전용 서브그래프 생성 (langchain.agents.create_agent 사용)"""
  logger.info("Creating Memo Agent Graph with langchain.agents.create_agent (checkpointer: %s)", "enabled" if checkpointer else "disabled")

  # 1. 도구 목록 정의
  tools = [add_memo_tool, update_memo_tool, delete_memo_tool, search_memo_tool, detect_intent_shift_tool]

  # 2. LLM 인스턴스 생성 (설정에서 memo_agent_node 정보 사용)
  # TODO : 아래 코드가 두줄다 있어야 하는 이유 개선
  llm_service = LLMServiceFactory.get_service("openai")
  model = llm_service.get_model_for_node("memo_agent_node")

  # 3. create_agent를 사용하여 그래프 빌드 및 컴파일
  # system_prompt를 통해 페르소나와 지침을 주입합니다.
  agent_graph = create_agent(
    model,
    tools=tools,
    system_prompt=SYSTEM_PROMPT,
    state_schema=RootState,
    checkpointer=checkpointer,
  )

  return agent_graph
