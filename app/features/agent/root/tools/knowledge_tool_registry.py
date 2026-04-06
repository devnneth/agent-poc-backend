from __future__ import annotations

from dataclasses import dataclass

from langchain_core.tools import StructuredTool

from app.features.agent.root.tools.knowledge_tool_factory import create_knowledge_rag_tools_from_knowledges
from app.features.knowledge.retrieval.retrieval_service import KnowledgeRetrievalService


# ==================================================================================================
# 지식 도구 캐시 엔트리
# --------------------------------------------------------------------------------------------------
# 사용자별로 구성된 지식 검색 도구의 캐시 저장 구조임
# ==================================================================================================
@dataclass
class KnowledgeToolCacheEntry:
  version: str
  tools: list[StructuredTool]
  tool_titles: list[str]


# ==================================================================================================
# 지식 도구 로드 결과
# --------------------------------------------------------------------------------------------------
# 현재 활성화된 도구 목록과 사용자 알림용 메타데이터를 담고 있음
# ==================================================================================================
@dataclass
class KnowledgeToolLoadResult:
  tools: list[StructuredTool]
  version: str
  tool_titles: list[str]
  cache_hit: bool
  should_notify: bool


# ==================================================================================================
# 지식 도구 레지스트리
# --------------------------------------------------------------------------------------------------
# 사용자별 지식 검색 도구 세트를 관리하고 변경 시 캐시를 갱신함
# ==================================================================================================
class KnowledgeToolRegistry:
  # ================================================================================================
  # 레지스트리 초기화
  # ------------------------------------------------------------------------------------------------
  # 지식 도구 관리를 위한 내부 저장소와 상태를 설정함
  # ================================================================================================
  def __init__(self):
    self._cache: dict[str, KnowledgeToolCacheEntry] = {}
    self._session_announced_versions: dict[str, str] = {}

  # ================================================================================================
  # 도구 목록 조회
  # ------------------------------------------------------------------------------------------------
  # 캐시를 활용하여 사용자가 접근 가능한 지식 검색 도구 세트를 반환함
  # ================================================================================================
  def get_tools(self, session, user_id: str, thread_id: str | None, retrieval_service: KnowledgeRetrievalService) -> KnowledgeToolLoadResult:
    current_version = retrieval_service.get_user_tool_version(session, user_id)
    cached = self._cache.get(user_id)
    tool_titles: list[str]
    cache_hit = cached is not None and cached.version == current_version
    if cache_hit and cached is not None:
      tools = cached.tools
      tool_titles = cached.tool_titles
    else:
      knowledges = retrieval_service.list_user_knowledges(session, user_id)
      tools = create_knowledge_rag_tools_from_knowledges(knowledges, retrieval_service)
      tool_titles = [knowledge.title for knowledge in knowledges]
      self._cache[user_id] = KnowledgeToolCacheEntry(version=current_version, tools=tools, tool_titles=tool_titles)

    should_notify = False
    if thread_id and tool_titles:
      announced_version = self._session_announced_versions.get(thread_id)
      should_notify = announced_version != current_version
      if should_notify:
        self._session_announced_versions[thread_id] = current_version

    return KnowledgeToolLoadResult(
      tools=tools,
      version=current_version,
      tool_titles=tool_titles,
      cache_hit=cache_hit,
      should_notify=should_notify,
    )

  # ================================================================================================
  # 사용자 캐시 초기화
  # ------------------------------------------------------------------------------------------------
  # 특정 사용자에 대해 저장된 지식 도구 캐시를 삭제함
  # ================================================================================================
  def clear_user(self, user_id: str) -> None:
    self._cache.pop(user_id, None)

  # ================================================================================================
  # 전체 캐시 초기화
  # ------------------------------------------------------------------------------------------------
  # 레지스트리에 저장된 모든 사용자별 도구 캐시를 제거함
  # ================================================================================================
  def clear_all(self) -> None:
    self._cache.clear()
    self._session_announced_versions.clear()


knowledge_tool_registry = KnowledgeToolRegistry()
