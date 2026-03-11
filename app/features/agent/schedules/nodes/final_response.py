import json
import logging
from pathlib import Path

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.types import Command

from app.features.agent.entity import ActionType
from app.features.agent.entity import AgentNodeName as Nodes
from app.features.agent.entity import HITLResultType
from app.features.agent.entity import ScheduleExtractedInfo
from app.features.agent.helpers.graph_helpers import apply_nostream
from app.features.agent.helpers.graph_helpers import get_llm
from app.features.agent.helpers.prompt import load_prompt
from app.features.agent.settings import AGENT_MODEL_SETTINGS as AMS
from app.features.agent.state import RootState

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

logger = logging.getLogger(__name__)


async def final_response_node(state: RootState, config: RunnableConfig) -> Command:
  """도구 실행 결과를 바탕으로 최종 사용자용 안내 메시지를 생성합니다."""
  user_confirmed = state.get("user_confirmed")
  messages = state.get("messages", [])

  # 시스템 프롬프트
  sys_msg = _resolve_final_response_node_prompt(state)

  # LLM 엔진 호출
  current_node = Nodes.FINAL_RESPONSE.value
  chain = apply_nostream(get_llm(current_node, config), AMS[current_node])

  # 최종 응답 생성
  response = await chain.ainvoke([sys_msg, *messages], config=config)

  # 승인된 액션(도구 실행 완료)인 경우에만 상태를 초기화하고, 거절 시에는 상태를 보존
  update_data = {"messages": [response], "user_confirmed": None}
  if user_confirmed == HITLResultType.APPROVE:
    update_data.update({"action": None, "schedule_slots": {}, "delete_result": None})

  # 리턴
  return Command(goto=END, update=update_data)


def _resolve_final_response_node_prompt(state: RootState) -> SystemMessage:
  """state에서 액션 타입에 따라 프롬프트를 구성하고 SystemMessage를 반환합니다."""
  action = state.get("action")
  schedule_slots = state.get("schedule_slots") or ScheduleExtractedInfo()
  user_confirmed = state.get("user_confirmed")
  messages = state.get("messages", [])
  delete_result = state.get("delete_result") or ""
  schedule_list = state.get("schedule_list") or []
  schedule_id = schedule_slots.schedule_id

  last_msg = messages[-1].content if messages else ""
  result_msg = last_msg if isinstance(last_msg, str) else ""
  result_json = schedule_slots.model_dump_json(exclude_none=True) if schedule_slots else "{}"

  logger.info(f"⭐[final_response_node] 최종응답. action: {action}")

  if action == ActionType.ADD:
    prompt_file = "final_response_add.txt"
    prompt_kwargs = {
      "action": action,
      "result_json": result_json,
      "result_msg": result_msg,
      "user_confirmed": user_confirmed,
    }
  elif action == ActionType.UPDATE:
    prompt_file = "final_response_update.txt"
    prompt_kwargs = {
      "action": action,
      "result_json": result_json,
      "result_msg": result_msg,
      "user_confirmed": user_confirmed,
      "schedule_id": schedule_id,
    }
  elif action == ActionType.DELETE:
    prompt_file = "final_response_del.txt"
    prompt_kwargs = {
      "action": action,
      "result_json": result_json,
      "result_msg": result_msg,
      "user_confirmed": user_confirmed,
      "schedule_id": schedule_id,
      "delete_result": delete_result,
    }
    logger.info(f"⭐[final_response_node] delete_result: {delete_result}")
  elif action == ActionType.SEARCH:
    prompt_file = "final_response_search.txt"
    prompt_kwargs = {
      "action": action,
      "result_msg": result_msg,
      "schedule_list": json.dumps(schedule_list, ensure_ascii=False),
    }
  else:
    # action이 None이거나 알 수 없는 경우 기존 공용 프롬프트 사용
    prompt_file = "final_response.txt"
    prompt_kwargs = {
      "action": action,
      "result_json": result_json,
      "result_msg": result_msg,
      "user_confirmed": user_confirmed,
      "schedule_list": json.dumps(schedule_list, ensure_ascii=False),
      "schedule_id": schedule_id,
    }

  return SystemMessage(content=load_prompt(PROMPTS_DIR / prompt_file).format(**prompt_kwargs))
