from typing import cast
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool

from app.features.agent.root.tools.knowledge_tool_factory import create_knowledge_rag_tools
from app.infrastructure.models.knowledge_model import KnowledgesModel


# ==================================================================================================
# 지식 도구 생성 테스트
# --------------------------------------------------------------------------------------------------
# 등록된 지식 데이터 개수만큼 각각 독립적인 검색 도구가 생성되는지 검증함
# ==================================================================================================
@pytest.mark.asyncio
async def test_create_knowledge_rag_tools_builds_one_tool_per_knowledge():
  knowledge_1 = KnowledgesModel(id=uuid4(), user_id="user-1", title="프로덕트 문서", description="제품 정책과 사용법")
  knowledge_2 = KnowledgesModel(id=uuid4(), user_id="user-1", title="개발 위키", description="개발 절차 모음")
  retrieval_service = MagicMock()
  retrieval_service.list_user_knowledges.return_value = [knowledge_1, knowledge_2]
  retrieval_service.search = AsyncMock(
    return_value=MagicMock(
      model_dump=MagicMock(
        return_value={
          "knowledge_id": str(knowledge_1.id),
          "knowledge_title": knowledge_1.title,
          "search_mode": "hybrid",
          "results": [],
        }
      )
    )
  )

  tools = create_knowledge_rag_tools(MagicMock(), "user-1", retrieval_service)

  assert len(tools) == 2
  assert tools[0].description == "제품 정책과 사용법"
  assert tools[1].description == "개발 절차 모음"
  assert tools[0].name != tools[1].name
  assert tools[0].name == f"knowledge_{knowledge_1.id.hex}"


# ==================================================================================================
# 지식 ID 고정 테스트
# --------------------------------------------------------------------------------------------------
# 생성된 지식 도구가 팩토리 시점의 특정 지식 ID를 클로저로 올바르게 캡처하는지 검증함
# ==================================================================================================
@pytest.mark.asyncio
async def test_knowledge_tool_uses_captured_knowledge_id():
  knowledge = KnowledgesModel(id=uuid4(), user_id="user-1", title="고객 지원", description="고객 지원 매뉴얼")
  retrieval_service = MagicMock()
  retrieval_service.list_user_knowledges.return_value = [knowledge]
  retrieval_service.search = AsyncMock(
    return_value=MagicMock(
      model_dump=MagicMock(
        return_value={
          "knowledge_id": str(knowledge.id),
          "knowledge_title": knowledge.title,
          "search_mode": "hybrid",
          "results": [],
        }
      )
    )
  )

  tools = create_knowledge_rag_tools(MagicMock(), "user-1", retrieval_service)
  tool = cast(StructuredTool, tools[0])
  tool_coroutine = tool.coroutine
  assert tool_coroutine is not None

  config = RunnableConfig(configurable={"db_session": MagicMock(spec=["exec"]), "user_id": "user-1"})

  result = await tool_coroutine(
    query="환불 정책",
    sparse_query="환불 정책",
    dense_query="refund policy",
    search_mode="hybrid",
    top_k=3,
    config=config,
  )

  assert result["knowledge_id"] == str(knowledge.id)
  retrieval_service.search.assert_awaited_once()
  assert retrieval_service.search.await_args.kwargs["knowledge_id"] == knowledge.id
  assert retrieval_service.search.await_args.kwargs["sparse_query"] == "환불 정책"
  assert retrieval_service.search.await_args.kwargs["dense_query"] == "refund policy"


# ==================================================================================================
# 지식 도구 인자 호출 테스트
# --------------------------------------------------------------------------------------------------
# 키워드 인자(kwargs) 형태의 호출에 대해서도 지식 도구가 정상 작동하는지 검증함
# ==================================================================================================
@pytest.mark.asyncio
async def test_knowledge_tool_accepts_schema_fields_as_kwargs():
  knowledge = KnowledgesModel(id=uuid4(), user_id="user-1", title="논문 가이드", description="논문 작성 절차")
  retrieval_service = MagicMock()
  retrieval_service.list_user_knowledges.return_value = [knowledge]
  retrieval_service.search = AsyncMock(
    return_value=MagicMock(
      model_dump=MagicMock(
        return_value={
          "knowledge_id": str(knowledge.id),
          "knowledge_title": knowledge.title,
          "search_mode": "hybrid",
          "results": [],
        }
      )
    )
  )

  tools = create_knowledge_rag_tools(MagicMock(), "user-1", retrieval_service)
  tool = cast(StructuredTool, tools[0])

  result = await tool.ainvoke(
    {"query": "논문 작성 순서", "sparse_query": "논문 작성 순서", "dense_query": "paper writing workflow", "search_mode": "hybrid", "top_k": 3},
    config=RunnableConfig(configurable={"db_session": MagicMock(spec=["exec"]), "user_id": "user-1"}),
  )

  assert result["knowledge_id"] == str(knowledge.id)
  retrieval_service.search.assert_awaited_once()
  assert retrieval_service.search.await_args.kwargs["query"] == "논문 작성 순서"
  assert retrieval_service.search.await_args.kwargs["sparse_query"] == "논문 작성 순서"
  assert retrieval_service.search.await_args.kwargs["dense_query"] == "paper writing workflow"
