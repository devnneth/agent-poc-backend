from langgraph.graph import START
from langgraph.graph import StateGraph

from app.features.agent.entity import AgentNodeName as Nodes
from app.features.agent.schedules.nodes.check_information.check_information import check_information_node
from app.features.agent.schedules.nodes.classify_schedule_action import classify_schedule_action_node
from app.features.agent.schedules.nodes.execute_tool import execute_tool_node
from app.features.agent.schedules.nodes.extract_information import extract_information_node
from app.features.agent.schedules.nodes.final_response import final_response_node
from app.features.agent.schedules.nodes.intent_shift import intent_shift_node
from app.features.agent.schedules.nodes.user_confirmation import user_confirmation_node
from app.features.agent.state import RootState


def get_schedule_graph() -> StateGraph:
  """
  일정 에이전트의 워크플로우를 구성합니다.
  """
  builder = StateGraph(RootState)

  # 노드 정의
  builder.add_node(Nodes.CLASSIFY_ACTION.value, classify_schedule_action_node)
  builder.add_node(Nodes.EXTRACT_INFO.value, extract_information_node)
  builder.add_node(Nodes.CHECK_INFO.value, check_information_node)
  builder.add_node(Nodes.INTENT_SHIFT.value, intent_shift_node)
  builder.add_node(Nodes.USER_CONFIRM.value, user_confirmation_node)
  builder.add_node(Nodes.EXECUTE_TOOL.value, execute_tool_node)
  builder.add_node(Nodes.FINAL_RESPONSE.value, final_response_node)

  # 진입점
  builder.add_edge(START, Nodes.CLASSIFY_ACTION.value)

  return builder
