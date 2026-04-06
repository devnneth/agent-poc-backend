from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.features.knowledge.retrieval.retrieval_service import KnowledgeChunkCandidate
from app.features.knowledge.retrieval.retrieval_service import KnowledgeRetrievalService
from app.infrastructure.models.knowledge_model import ProcessingStatus


# ==================================================================================================
# 검색 후보 생성
# --------------------------------------------------------------------------------------------------
# 테스트를 위한 모의 검색 후보 청크 생성
# ==================================================================================================
def _candidate(
  *,
  knowledge_id,
  knowledge_title: str,
  chunk_index: int,
  content: str,
  embedding: list[float],
):
  return KnowledgeChunkCandidate(
    knowledge_id=knowledge_id,
    knowledge_title=knowledge_title,
    chunk_id=uuid4(),
    source_id=uuid4(),
    display_name=f"source-{chunk_index}",
    chunk_index=chunk_index,
    content=content,
    embedding=embedding,
    chunk_metadata={"section": chunk_index},
  )


# ==================================================================================================
# Dense 검색 정렬 테스트
# --------------------------------------------------------------------------------------------------
# Dense 검색이 코사인 유사도 순으로 결과를 반환하는지 검증
# ==================================================================================================
@pytest.mark.asyncio
async def test_dense_search_returns_chunks_sorted_by_cosine_similarity():
  knowledge_id = uuid4()
  embedding_service = MagicMock()
  embedding_service.embedding = AsyncMock(return_value=[1.0, 0.0])
  service = KnowledgeRetrievalService(embedding_service=embedding_service)

  candidates = [
    _candidate(knowledge_id=knowledge_id, knowledge_title="제품 문서", chunk_index=0, content="첫 문단", embedding=[1.0, 0.0]),
    _candidate(knowledge_id=knowledge_id, knowledge_title="제품 문서", chunk_index=1, content="둘째 문단", embedding=[0.0, 1.0]),
  ]

  service._load_candidates = MagicMock(return_value=candidates)  # type: ignore[method-assign]
  result = await service.search_dense(MagicMock(), "user-1", knowledge_id, "제품 설치", top_k=2)

  assert [item.chunk_index for item in result.results] == [0, 1]
  assert result.search_mode == "dense"
  embedding_service.embedding.assert_awaited_once_with("제품 설치")


# ==================================================================================================
# Sparse 검색 매칭 테스트
# --------------------------------------------------------------------------------------------------
# Sparse 검색이 질의 토큰과 일치하는 청크만 정확히 반환하는지 검증
# ==================================================================================================
def test_sparse_search_returns_only_matching_chunks():
  knowledge_id = uuid4()
  embedding_service = MagicMock()
  service = KnowledgeRetrievalService(embedding_service=embedding_service)

  candidates = [
    _candidate(knowledge_id=knowledge_id, knowledge_title="가이드", chunk_index=0, content="설치 가이드와 실행 방법", embedding=[1.0, 0.0]),
    _candidate(knowledge_id=knowledge_id, knowledge_title="가이드", chunk_index=1, content="결제 정책 안내", embedding=[0.0, 1.0]),
  ]

  service._load_candidates = MagicMock(return_value=candidates)  # type: ignore[method-assign]
  result = service.search_sparse(MagicMock(), "user-1", knowledge_id, "설치 방법", top_k=5)

  assert [item.chunk_index for item in result.results] == [0]
  assert result.search_mode == "sparse"


# ==================================================================================================
# Hybrid 검색 결과 융합 테스트
# --------------------------------------------------------------------------------------------------
# Sparse와 Dense 검색 결과를 적절히 결합하여 반환하는지 검증
# ==================================================================================================
@pytest.mark.asyncio
async def test_hybrid_search_fuses_sparse_and_dense_results():
  knowledge_id = uuid4()
  embedding_service = MagicMock()
  embedding_service.embedding = AsyncMock(return_value=[1.0, 0.0])
  service = KnowledgeRetrievalService(embedding_service=embedding_service)

  sparse_best = _candidate(knowledge_id=knowledge_id, knowledge_title="운영 문서", chunk_index=0, content="배포 절차와 배포 체크리스트", embedding=[0.1, 0.9])
  dense_best = _candidate(knowledge_id=knowledge_id, knowledge_title="운영 문서", chunk_index=1, content="시스템 아키텍처", embedding=[1.0, 0.0])

  service._load_candidates = MagicMock(return_value=[sparse_best, dense_best])  # type: ignore[method-assign]
  result = await service.search_hybrid(MagicMock(), "user-1", knowledge_id, "배포 아키텍처", top_k=2)

  assert len(result.results) == 2
  assert {item.chunk_index for item in result.results} == {0, 1}
  assert result.search_mode == "hybrid"


# ==================================================================================================
# Hybrid 검색 질의 분리 테스트
# --------------------------------------------------------------------------------------------------
# Hybrid 검색 시 각 엔진에 맞는 분리된 질의문을 사용하는지 검증
# ==================================================================================================
@pytest.mark.asyncio
async def test_search_uses_split_queries_for_hybrid_mode():
  knowledge_id = uuid4()
  service = KnowledgeRetrievalService(embedding_service=MagicMock())

  with (
    patch.object(service, "_load_candidates", return_value=[]),
    patch.object(service, "_resolve_knowledge_title", return_value="논문 가이드"),
    patch.object(service, "_rank_sparse_candidates", return_value=[]) as mock_sparse,
    patch.object(service, "_rank_dense_candidates", new_callable=AsyncMock, return_value=[]) as mock_dense,
  ):
    await service.search(
      MagicMock(),
      "user-1",
      knowledge_id,
      query="원문 질문",
      sparse_query="원문 키워드",
      dense_query="semantic rewrite",
      search_mode="hybrid",
      top_k=3,
    )

  mock_sparse.assert_called_once_with([], "원문 키워드", 9)
  mock_dense.assert_awaited_once_with([], "semantic rewrite", 9)


# ==================================================================================================
# 질의 분리 실패 폴백 테스트
# --------------------------------------------------------------------------------------------------
# 질의 분리가 불가능할 때 원본 질의를 재사용하여 검색을 수행하는지 검증
# ==================================================================================================
@pytest.mark.asyncio
async def test_search_falls_back_to_query_when_split_queries_missing():
  knowledge_id = uuid4()
  service = KnowledgeRetrievalService(embedding_service=MagicMock())

  with (
    patch.object(service, "_load_candidates", return_value=[]),
    patch.object(service, "_resolve_knowledge_title", return_value="논문 가이드"),
    patch.object(service, "_rank_sparse_candidates", return_value=[]) as mock_sparse,
    patch.object(service, "_rank_dense_candidates", new_callable=AsyncMock, return_value=[]) as mock_dense,
  ):
    await service.search(
      MagicMock(),
      "user-1",
      knowledge_id,
      query="원문 질문",
      sparse_query="  ",
      dense_query=None,
      search_mode="hybrid",
      top_k=2,
    )

  mock_sparse.assert_called_once_with([], "원문 질문", 6)
  mock_dense.assert_awaited_once_with([], "원문 질문", 6)


# ==================================================================================================
# 검색 스코프 필터 검증
# --------------------------------------------------------------------------------------------------
# 검색 쿼리에 사용자 및 지식 스코프, 상태 필터가 포함되는지 검증
# ==================================================================================================
def test_candidate_query_contains_knowledge_scope_filters():
  knowledge_id = uuid4()
  service = KnowledgeRetrievalService(embedding_service=MagicMock())

  stmt = service._build_candidate_query("user-1", knowledge_id)
  compiled = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))

  assert "knowledges.id" in compiled
  assert str(knowledge_id) in compiled
  assert "knowledges.is_rag_enabled" in compiled
  assert "knowledge_sources.is_rag_enabled" in compiled
  assert "knowledge_sources.processing_status" in compiled
  assert ProcessingStatus.DONE.value in compiled
  assert "deleted_at IS NULL" in compiled


# ==================================================================================================
# 완료된 지식 목록 필터링 테스트
# --------------------------------------------------------------------------------------------------
# 지식 목록 조회 시 처리가 완료된 항목만 반환하는지 검증
# ==================================================================================================
def test_list_user_knowledges_filters_only_knowledges_with_done_sources():
  service = KnowledgeRetrievalService(embedding_service=MagicMock())
  session = MagicMock()
  session.exec.return_value.all.return_value = []

  service.list_user_knowledges(session, "user-1")

  stmt = session.exec.call_args.args[0]
  compiled = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))

  assert "EXISTS" in compiled
  assert "knowledge_chunks.source_id IN" in compiled
  assert "knowledge_sources.knowledge_id = knowledges.id" in compiled
  assert "knowledges.is_rag_enabled" in compiled
  assert "knowledge_sources.is_rag_enabled" in compiled
  assert "knowledge_sources.processing_status" in compiled
  assert ProcessingStatus.DONE.value in compiled
  assert "knowledge_sources.deleted_at IS NULL" in compiled


# ==================================================================================================
# 도구 버전 갱신 테스트
# --------------------------------------------------------------------------------------------------
# 지식 정보 변경 시 도구의 버전 정보가 함께 갱신되는지 검증
# ==================================================================================================
def test_get_user_tool_version_changes_when_updated_at_changes():
  service = KnowledgeRetrievalService(embedding_service=MagicMock())
  knowledge_id = uuid4()
  first_knowledge = MagicMock(id=knowledge_id)
  first_knowledge.updated_at.isoformat.return_value = "2026-03-27T10:00:00+00:00"
  second_knowledge = MagicMock(id=knowledge_id)
  second_knowledge.updated_at.isoformat.return_value = "2026-03-27T11:00:00+00:00"

  with patch.object(service, "list_user_knowledges", side_effect=[[first_knowledge], [second_knowledge]]):
    first_version = service.get_user_tool_version(MagicMock(), "user-1")
    second_version = service.get_user_tool_version(MagicMock(), "user-1")

  assert first_version != second_version
