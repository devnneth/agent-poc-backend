import logging
from typing import Any
from typing import cast
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from langchain_core.tools import tool

from app.features.knowledge.retrieval.retrieval_entity import KnowledgeSearchInput
from app.features.knowledge.retrieval.retrieval_service import KnowledgeRetrievalService
from app.infrastructure.models.knowledge_model import KnowledgesModel

logger = logging.getLogger(__name__)


# ==================================================================================================
# 지식 RAG 도구 생성
# --------------------------------------------------------------------------------------------------
# 사용자의 모든 지식 소스에 대해 각각의 검색 도구를 생성함
# ==================================================================================================
def create_knowledge_rag_tools(session, user_id: str, retrieval_service: KnowledgeRetrievalService) -> list[StructuredTool]:
  knowledges = retrieval_service.list_user_knowledges(session, user_id)
  return create_knowledge_rag_tools_from_knowledges(knowledges, retrieval_service)


# ==================================================================================================
# 지식 목록 기반 RAG 도구 생성
# --------------------------------------------------------------------------------------------------
# 로드된 지식 리스트를 바탕으로 검색용 도구 세트를 구성함
# ==================================================================================================
def create_knowledge_rag_tools_from_knowledges(knowledges: list[KnowledgesModel], retrieval_service: KnowledgeRetrievalService) -> list[StructuredTool]:
  return [_build_knowledge_rag_tool(knowledge, retrieval_service) for knowledge in knowledges]


# ==================================================================================================
# 단일 지식 RAG 도구 빌더
# --------------------------------------------------------------------------------------------------
# 특정 지식 소스 하나를 검색하기 위한 개별 도구를 생성함
# ==================================================================================================
def _build_knowledge_rag_tool(knowledge: KnowledgesModel, retrieval_service: KnowledgeRetrievalService) -> StructuredTool:
  tool_name = _build_tool_name(knowledge.title, knowledge.id)

  # ------------------------------------------------------------------------------------------------
  # 도구 설명 구성
  # ------------------------------------------------------------------------------------------------
  # 제목과 상세 설명을 조합하여 LLM이 검색 대상을 명확히 인지하도록 함
  # ------------------------------------------------------------------------------------------------
  base_description = knowledge.description.strip()
  tool_description = f"지식 제목: {knowledge.title}\n설명: {base_description}" if base_description else f"'{knowledge.title}' 지식 저장소를 검색합니다."

  # ------------------------------------------------------------------------------------------------
  # 지식 검색 도구
  # ------------------------------------------------------------------------------------------------
  @tool(tool_name, args_schema=KnowledgeSearchInput, description=tool_description)
  async def search_knowledge_tool(
    query: str,
    sparse_query: str | None = None,
    dense_query: str | None = None,
    top_k: int = 5,
    *,
    config: RunnableConfig,
  ) -> dict[str, Any]:
    # LangGraph ToolNode는 args_schema 필드를 개별 kwargs로 전달하므로
    # BaseModel 단일 인자를 기대하지 않고 시그니처를 스키마와 동일하게 유지합니다.
    configurable = config.get("configurable") or {}
    db_session = configurable.get("db_session")
    runtime_user_id = configurable.get("user_id")

    if db_session is None or not hasattr(db_session, "exec"):
      raise ValueError("knowledge tool 실행에 필요한 db_session을 찾을 수 없습니다.")
    if not isinstance(runtime_user_id, str) or not runtime_user_id:
      raise ValueError("knowledge tool 실행에 필요한 user_id를 찾을 수 없습니다.")

    logger.info(
      "⭐[Knowledge Tool Call] Collection: '%s' (ID: %s), Top-K: %s, Query: %s",
      knowledge.title,
      knowledge.id,
      top_k,
      query,
    )

    result = await retrieval_service.search(
      session=db_session,
      user_id=runtime_user_id,
      knowledge_id=knowledge.id,
      query=query,
      sparse_query=sparse_query,
      dense_query=dense_query,
      search_mode="hybrid",
      top_k=top_k,
    )
    payload = result.model_dump(mode="json")
    return payload

  return cast(StructuredTool, search_knowledge_tool)


# ==================================================================================================
# 도구 이름 생성
# --------------------------------------------------------------------------------------------------
# 레지스트리 내 충돌 방지를 위해 지식 기반의 고유 도구 명칭을 생성함
# ==================================================================================================
def _build_tool_name(title: str, knowledge_id: UUID) -> str:
  return f"knowledge_{knowledge_id.hex}"
