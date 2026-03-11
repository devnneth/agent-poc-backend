from langgraph.graph import START
from langgraph.graph import StateGraph

from app.features.agent.entity import AgentNodeName as Nodes
from app.features.agent.memo.memo_agent import create_memo_agent_graph
from app.features.agent.root.nodes.general_conversation import general_conversation_node
from app.features.agent.root.nodes.root_intent import root_intent_node
from app.features.agent.schedules.schedule_graph import get_schedule_graph
from app.features.agent.state import RootState
from app.features.agent.todo.todo_agent import create_todo_agent_graph
from app.infrastructure.persistence.checkpointer import checkpointer

ROOT_ROUTER_CACHE = {}


async def get_router_graph():
  """라우터 그래프를 지연 초기화하여 반환합니다."""
  if "root" not in ROOT_ROUTER_CACHE:
    actual_saver = await checkpointer.get_checkpointer()
    ROOT_ROUTER_CACHE["root"] = build_router_graph(checkpointer=actual_saver)
  return ROOT_ROUTER_CACHE["root"]


def build_router_graph(checkpointer):
  """상위 라우터 에이전트용 다이얼로그 그래프 빌더"""
  builder = StateGraph(RootState)
  schedule_graph = get_schedule_graph()
  todo_graph = create_todo_agent_graph(checkpointer=checkpointer)
  memo_graph = create_memo_agent_graph(checkpointer=checkpointer)

  # 노드 정의
  builder.add_node(Nodes.ROOT_INTENT.value, root_intent_node)
  builder.add_node(Nodes.GENERAL_CONVERSATION.value, general_conversation_node)
  builder.add_node(Nodes.SCHEDULE_AGENT.value, schedule_graph.compile())
  builder.add_node(Nodes.TODO_AGENT.value, todo_graph)
  builder.add_node(Nodes.MEMO_AGENT.value, memo_graph)

  # 엣지 연결
  builder.add_edge(START, Nodes.ROOT_INTENT.value)

  return builder.compile(checkpointer=checkpointer)
