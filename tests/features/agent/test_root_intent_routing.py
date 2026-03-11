from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from app.features.agent.entity import AgentNodeName
from app.features.agent.entity import RouterIntent
from app.features.agent.root.nodes.root_intent import RootIntentResult
from app.features.agent.root.nodes.root_intent import root_intent_node
from app.features.agent.state import RootState
from app.features.llm.llm_service import LLMServiceFactory


@pytest.mark.asyncio
async def test_root_analyze_intent_node_routes_schedule_followup_request():
  """일정 검색 직후의 후속 삭제 요청이 구조화 출력으로 일정 노드에 라우팅되는지 확인합니다."""
  state: RootState = {
    "messages": [
      HumanMessage(content="일정 검색 결과를 보고 판단해줘."),
      AIMessage(content="검색 결과입니다. 34번 일정이 있습니다."),
      HumanMessage(content="34번을 삭제해줘"),
    ],
  }
  config: RunnableConfig = {"configurable": {"thread_id": "test_thread"}}

  mock_service = MagicMock()
  mock_model = MagicMock()
  mock_structured_llm = MagicMock()
  mock_structured_llm.ainvoke = AsyncMock(return_value=RootIntentResult(intent=RouterIntent.SCHEDULE_AGENT))
  mock_structured_llm.with_config.return_value = mock_structured_llm
  mock_model.with_structured_output.return_value = mock_structured_llm
  mock_service.get_model_for_node.return_value = mock_model

  with patch.object(LLMServiceFactory, "get_service", return_value=mock_service):
    result = await root_intent_node(state, config)

  mock_model.with_structured_output.assert_called_once_with(RootIntentResult, method="function_calling")
  assert result.goto == AgentNodeName.SCHEDULE_AGENT


@pytest.mark.asyncio
async def test_root_analyze_intent_node_routes_todo_add_request():
  """명시적인 할일 추가 요청이 todo_agent로 라우팅되는지 확인합니다."""
  state: RootState = {
    "messages": [
      HumanMessage(content="입사지원하라고 할일을 추가해줘"),
    ],
  }
  config: RunnableConfig = {"configurable": {"thread_id": "test_thread"}}

  mock_service = MagicMock()
  mock_model = MagicMock()
  mock_structured_llm = MagicMock()
  mock_structured_llm.ainvoke = AsyncMock(return_value=RootIntentResult(intent=RouterIntent.TODO_AGENT))
  mock_structured_llm.with_config.return_value = mock_structured_llm
  mock_model.with_structured_output.return_value = mock_structured_llm
  mock_service.get_model_for_node.return_value = mock_model

  with patch.object(LLMServiceFactory, "get_service", return_value=mock_service):
    result = await root_intent_node(state, config)

  assert result.goto == AgentNodeName.TODO_AGENT


@pytest.mark.asyncio
async def test_root_analyze_intent_node_routes_todo_search_request():
  """할일 조회 요청이 todo_agent로 라우팅되는지 확인합니다."""
  state: RootState = {
    "messages": [
      HumanMessage(content="할일 조회해줘"),
    ],
  }
  config: RunnableConfig = {"configurable": {"thread_id": "test_thread"}}

  mock_service = MagicMock()
  mock_model = MagicMock()
  mock_structured_llm = MagicMock()
  mock_structured_llm.ainvoke = AsyncMock(return_value=RootIntentResult(intent=RouterIntent.TODO_AGENT))
  mock_structured_llm.with_config.return_value = mock_structured_llm
  mock_model.with_structured_output.return_value = mock_structured_llm
  mock_service.get_model_for_node.return_value = mock_model

  with patch.object(LLMServiceFactory, "get_service", return_value=mock_service):
    result = await root_intent_node(state, config)

  assert result.goto == AgentNodeName.TODO_AGENT


@pytest.mark.asyncio
async def test_root_analyze_intent_node_routes_memo_request():
  """명시적인 메모 요청이 memo_agent로 라우팅되는지 확인합니다."""
  state: RootState = {
    "messages": [
      HumanMessage(content="회의 메모 찾아줘"),
    ],
  }
  config: RunnableConfig = {"configurable": {"thread_id": "test_thread"}}

  mock_service = MagicMock()
  mock_model = MagicMock()
  mock_structured_llm = MagicMock()
  mock_structured_llm.ainvoke = AsyncMock(return_value=RootIntentResult(intent=RouterIntent.MEMO_AGENT))
  mock_structured_llm.with_config.return_value = mock_structured_llm
  mock_model.with_structured_output.return_value = mock_structured_llm
  mock_service.get_model_for_node.return_value = mock_model

  with patch.object(LLMServiceFactory, "get_service", return_value=mock_service):
    result = await root_intent_node(state, config)

  assert result.goto == AgentNodeName.MEMO_AGENT


@pytest.mark.asyncio
async def test_root_analyze_intent_node_short_circuits_explicit_memo_request_after_todo_reject():
  """할일 수정 거절 직후라도 '메모 조회'는 규칙 기반으로 memo_agent에 라우팅되어야 합니다."""
  state: RootState = {
    "messages": [
      HumanMessage(content="할일 조회"),
      AIMessage(content="현재 등록된 할일 목록입니다."),
      HumanMessage(content="7번 수정"),
      AIMessage(content="할일 수정 작업을 승인해주세요"),
      HumanMessage(content='{"todo_id":7,"user_confirmed":"reject"}'),
      AIMessage(content="요청하신 일정 수정 작업이 취소되었습니다."),
      HumanMessage(content="메모 조회"),
    ],
  }
  config: RunnableConfig = {"configurable": {"thread_id": "test_thread"}}

  mock_service = MagicMock()
  mock_model = MagicMock()
  mock_structured_llm = MagicMock()
  mock_structured_llm.ainvoke = AsyncMock(return_value=RootIntentResult(intent=RouterIntent.GENERAL_CONVERSATION))
  mock_structured_llm.with_config.return_value = mock_structured_llm
  mock_model.with_structured_output.return_value = mock_structured_llm
  mock_service.get_model_for_node.return_value = mock_model

  with patch.object(LLMServiceFactory, "get_service", return_value=mock_service):
    result = await root_intent_node(state, config)

  assert result.goto == AgentNodeName.MEMO_AGENT
  mock_model.with_structured_output.assert_not_called()
