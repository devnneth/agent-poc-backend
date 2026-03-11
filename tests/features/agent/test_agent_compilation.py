from app.features.agent.root.root_graph import build_router_graph
from app.features.agent.schedules.schedule_graph import get_schedule_graph


def test_router_graph_compilation():
  """상위 라우터 에이전트 그래프가 정상적으로 컴파일되는지 확인합니다."""
  graph = build_router_graph(checkpointer=None)
  assert graph is not None

  # START -> ROOT_ANALYZE_INTENT 연결 확인
  edges = graph.get_graph().edges
  start_edge = next((e for e in edges if e.source == "__start__"), None)
  assert start_edge is not None
  assert start_edge.target == "root_intent_node"


def test_schedule_graph_compilation():
  """하위 일정 에이전트 그래프가 정상적으로 컴파일되는지 확인합니다."""
  graph = get_schedule_graph().compile()
  assert graph is not None
