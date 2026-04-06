from __future__ import annotations

import hashlib
import logging
import math
import re
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from app.features.knowledge.retrieval.retrieval_entity import KnowledgeSearchMode
from app.features.knowledge.retrieval.retrieval_entity import KnowledgeSearchResult
from app.features.knowledge.retrieval.retrieval_entity import KnowledgeSearchResultItem
from app.infrastructure.models.knowledge_model import KnowledgeChunksModel
from app.infrastructure.models.knowledge_model import KnowledgesModel
from app.infrastructure.models.knowledge_model import KnowledgeSourcesModel
from app.infrastructure.models.knowledge_model import ProcessingStatus

logger = logging.getLogger(__name__)

_TOKEN_PATTERN = re.compile(r"[0-9A-Za-z가-힣]+")
_RRF_K = 60


# ==================================================================================================
# 질의 임베딩 게이트웨이 인터페이스
# --------------------------------------------------------------------------------------------------
# 질의문 임베딩 서비스가 만족해야 하는 최소 인터페이스를 정의합니다
# ==================================================================================================
class QueryEmbeddingGateway(Protocol):
  # ================================================================================================
  # 질의 임베딩 생성
  # ------------------------------------------------------------------------------------------------
  # 검색 질의 텍스트를 벡터로 변환합니다
  # ================================================================================================
  async def embedding(self, texts: str) -> list[float] | None: ...


# ==================================================================================================
# 지식 청크 후보
# --------------------------------------------------------------------------------------------------
# 검색 연산의 대상이 되는 지식 청크 데이터 모델입니다
# ==================================================================================================
@dataclass(frozen=True)
class KnowledgeChunkCandidate:
  knowledge_id: UUID
  knowledge_title: str
  chunk_id: UUID
  source_id: UUID
  display_name: str
  chunk_index: int
  content: str
  embedding: list[float]
  chunk_metadata: dict | list | None


# ==================================================================================================
# 지식 검색 서비스
# --------------------------------------------------------------------------------------------------
# 지식 문서에 대한 희소, 밀집, 하이브리드 검색 기능을 통합 제공합니다
# ==================================================================================================
class KnowledgeRetrievalService:
  # ================================================================================================
  # 초기화
  # ------------------------------------------------------------------------------------------------
  # 검색 및 임베딩 처리에 필요한 의존성을 설정합니다
  # ================================================================================================
  def __init__(self, embedding_service: QueryEmbeddingGateway):
    self._embedding_service = embedding_service

  # ================================================================================================
  # 사용자 지식 목록 조회
  # ------------------------------------------------------------------------------------------------
  # 사용자가 접근하여 검색할 수 있는 지식 저장소 목록을 조회합니다
  # ================================================================================================
  def list_user_knowledges(self, session: Session, user_id: str) -> list[KnowledgesModel]:
    searchable_source_ids = select(KnowledgeSourcesModel.id).where(
      col(KnowledgeSourcesModel.knowledge_id) == col(KnowledgesModel.id),
      col(KnowledgeSourcesModel.user_id) == user_id,
      col(KnowledgeSourcesModel.is_rag_enabled).is_(True),
      col(KnowledgeSourcesModel.deleted_at).is_(None),
      col(KnowledgeSourcesModel.processing_status) == ProcessingStatus.DONE,
    )
    has_searchable_content = (
      select(KnowledgeChunksModel.id)
      .where(
        col(KnowledgeChunksModel.user_id) == user_id,
        col(KnowledgeChunksModel.source_id).in_(searchable_source_ids),
      )
      .exists()
    )
    stmt = (
      select(KnowledgesModel)
      .where(
        col(KnowledgesModel.user_id) == user_id,
        col(KnowledgesModel.is_rag_enabled).is_(True),
        col(KnowledgesModel.deleted_at).is_(None),
        has_searchable_content,
      )
      .order_by(col(KnowledgesModel.created_at).asc())
    )
    return list(session.exec(stmt).all())

  # ================================================================================================
  # 도구 버전 생성
  # ------------------------------------------------------------------------------------------------
  # 검색 가능한 지식 도구 집합의 변경 여부를 판단하기 위한 버전 문자열을 생성합니다
  # ================================================================================================
  def get_user_tool_version(self, session: Session, user_id: str) -> str:
    knowledges = self.list_user_knowledges(session, user_id)
    signature_source = "|".join(f"{knowledge.id}:{knowledge.updated_at.isoformat()}" for knowledge in knowledges)
    return hashlib.sha256(signature_source.encode("utf-8")).hexdigest()

  # ================================================================================================
  # 희소 검색
  # ------------------------------------------------------------------------------------------------
  # 키워드 기반의 텍스트 매칭 검색을 수행합니다
  # ================================================================================================
  def search_sparse(self, session: Session, user_id: str, knowledge_id: UUID, query: str, top_k: int = 5) -> KnowledgeSearchResult:
    candidates = self._load_candidates(session, user_id, knowledge_id)
    knowledge_title = self._resolve_knowledge_title(candidates, knowledge_id)
    ranked = self._rank_sparse_candidates(candidates, query, top_k)
    return self._build_result(knowledge_id, knowledge_title, "sparse", ranked)

  # ================================================================================================
  # 밀집 검색
  # ------------------------------------------------------------------------------------------------
  # 벡터 유사도 기반의 의미론적 검색을 수행합니다
  # ================================================================================================
  async def search_dense(self, session: Session, user_id: str, knowledge_id: UUID, query: str, top_k: int = 5) -> KnowledgeSearchResult:
    candidates = self._load_candidates(session, user_id, knowledge_id)
    knowledge_title = self._resolve_knowledge_title(candidates, knowledge_id)
    ranked = await self._rank_dense_candidates(candidates, query, top_k)
    return self._build_result(knowledge_id, knowledge_title, "dense", ranked)

  # ================================================================================================
  # 하이브리드 검색
  # ------------------------------------------------------------------------------------------------
  # 희소 검색과 밀집 검색 결과를 결합하여 최적의 순위를 도출합니다
  # ================================================================================================
  async def search_hybrid(self, session: Session, user_id: str, knowledge_id: UUID, query: str, top_k: int = 5) -> KnowledgeSearchResult:
    candidates = self._load_candidates(session, user_id, knowledge_id)
    knowledge_title = self._resolve_knowledge_title(candidates, knowledge_id)
    sparse_ranked = self._rank_sparse_candidates(candidates, query, max(top_k * 3, top_k))
    dense_ranked = await self._rank_dense_candidates(candidates, query, max(top_k * 3, top_k))
    fused = self._fuse_ranked_results(sparse_ranked, dense_ranked, top_k)
    return self._build_result(knowledge_id, knowledge_title, "hybrid", fused)

  # ================================================================================================
  # 검색 분기 처리
  # ------------------------------------------------------------------------------------------------
  # 요청된 모드에 맞춰 적절한 검색 로직을 실행합니다
  # ================================================================================================
  async def search(
    self,
    session: Session,
    user_id: str,
    knowledge_id: UUID,
    query: str,
    sparse_query: str | None = None,
    dense_query: str | None = None,
    search_mode: KnowledgeSearchMode = "hybrid",
    top_k: int = 5,
  ) -> KnowledgeSearchResult:
    normalized_query = query.strip()
    if not normalized_query:
      raise ValueError("knowledge 검색어는 비어 있을 수 없습니다.")
    if top_k < 1:
      raise ValueError("top_k는 1 이상이어야 합니다.")

    normalized_sparse_query = self._normalize_optional_query(sparse_query) or normalized_query
    normalized_dense_query = self._normalize_optional_query(dense_query) or normalized_query

    if search_mode == "sparse":
      return self.search_sparse(session, user_id, knowledge_id, normalized_sparse_query, top_k)
    if search_mode == "dense":
      return await self.search_dense(session, user_id, knowledge_id, normalized_dense_query, top_k)
    return await self.search_hybrid_with_queries(
      session,
      user_id,
      knowledge_id,
      sparse_query=normalized_sparse_query,
      dense_query=normalized_dense_query,
      top_k=top_k,
    )

  # ================================================================================================
  # 질의 분리형 하이브리드 검색
  # ------------------------------------------------------------------------------------------------
  # 서로 다른 검색 엔진용 질의문을 사용하여 하이브리드 검색을 수행합니다
  # ================================================================================================
  async def search_hybrid_with_queries(
    self,
    session: Session,
    user_id: str,
    knowledge_id: UUID,
    sparse_query: str,
    dense_query: str,
    top_k: int = 5,
  ) -> KnowledgeSearchResult:
    candidates = self._load_candidates(session, user_id, knowledge_id)
    knowledge_title = self._resolve_knowledge_title(candidates, knowledge_id)
    sparse_ranked = self._rank_sparse_candidates(candidates, sparse_query, max(top_k * 3, top_k))
    dense_ranked = await self._rank_dense_candidates(candidates, dense_query, max(top_k * 3, top_k))
    fused = self._fuse_ranked_results(sparse_ranked, dense_ranked, top_k)
    return self._build_result(knowledge_id, knowledge_title, "hybrid", fused)

  # ================================================================================================
  # 검색 후보 쿼리 생성
  # ------------------------------------------------------------------------------------------------
  # 검색 범위 내의 후보군을 선별하기 위한 공통 SQL 쿼리를 구성합니다
  # ================================================================================================
  def _build_candidate_query(self, user_id: str, knowledge_id: UUID):
    return (
      select(KnowledgeChunksModel, KnowledgeSourcesModel, KnowledgesModel)
      .join(KnowledgeSourcesModel, col(KnowledgeChunksModel.source_id) == col(KnowledgeSourcesModel.id))
      .join(KnowledgesModel, col(KnowledgeSourcesModel.knowledge_id) == col(KnowledgesModel.id))
      .where(
        col(KnowledgeChunksModel.user_id) == user_id,
        col(KnowledgeSourcesModel.user_id) == user_id,
        col(KnowledgesModel.user_id) == user_id,
        col(KnowledgesModel.id) == knowledge_id,
        col(KnowledgesModel.is_rag_enabled).is_(True),
        col(KnowledgesModel.deleted_at).is_(None),
        col(KnowledgeSourcesModel.is_rag_enabled).is_(True),
        col(KnowledgeSourcesModel.deleted_at).is_(None),
        col(KnowledgeSourcesModel.processing_status) == ProcessingStatus.DONE,
      )
      .order_by(col(KnowledgeSourcesModel.created_at).asc(), col(KnowledgeChunksModel.chunk_index).asc())
    )

  # ================================================================================================
  # 검색 후보 로드
  # ------------------------------------------------------------------------------------------------
  # DB에서 검색 대상이 될 청크 후보들을 읽어옵니다
  # ================================================================================================
  def _load_candidates(self, session: Session, user_id: str, knowledge_id: UUID) -> list[KnowledgeChunkCandidate]:
    rows = session.exec(self._build_candidate_query(user_id, knowledge_id)).all()
    candidates: list[KnowledgeChunkCandidate] = []

    for chunk, source, knowledge in rows:
      candidates.append(
        KnowledgeChunkCandidate(
          knowledge_id=knowledge.id,
          knowledge_title=knowledge.title,
          chunk_id=chunk.id,
          source_id=source.id,
          display_name=source.display_name,
          chunk_index=chunk.chunk_index,
          content=chunk.chunk_content,
          embedding=list(chunk.embedding),
          chunk_metadata=chunk.chunk_metadata,
        )
      )

    return candidates

  # ================================================================================================
  # 지식 제목 식별
  # ------------------------------------------------------------------------------------------------
  # 검색 결과 후보에서 연관된 지식 문서의 제목을 추출합니다
  # ================================================================================================
  def _resolve_knowledge_title(self, candidates: list[KnowledgeChunkCandidate], knowledge_id: UUID) -> str:
    if candidates:
      return candidates[0].knowledge_title
    raise ValueError(f"검색 가능한 knowledge를 찾을 수 없습니다: {knowledge_id}")

  # ================================================================================================
  # 희소 검색 순위 산정
  # ------------------------------------------------------------------------------------------------
  # 질의문과 본문의 토큰 일치도를 기준으로 점수를 계산합니다
  # ================================================================================================
  def _rank_sparse_candidates(
    self,
    candidates: list[KnowledgeChunkCandidate],
    query: str,
    top_k: int,
  ) -> list[tuple[KnowledgeChunkCandidate, float]]:
    normalized_query = query.strip().casefold()
    query_tokens = self._tokenize(normalized_query)
    if not query_tokens:
      raise ValueError("knowledge 검색어에서 유효한 토큰을 추출하지 못했습니다.")

    scored: list[tuple[KnowledgeChunkCandidate, float]] = []
    for candidate in candidates:
      content = candidate.content.casefold()
      content_tokens = set(self._tokenize(content))
      token_matches = len(query_tokens & content_tokens)
      if token_matches == 0 and normalized_query not in content:
        continue

      phrase_bonus = 1.0 if normalized_query in content else 0.0
      score = phrase_bonus + (token_matches / len(query_tokens))
      scored.append((candidate, score))

    scored.sort(key=lambda item: (-item[1], item[0].chunk_index, item[0].display_name))
    return scored[:top_k]

  # ================================================================================================
  # 밀집 검색 순위 산정
  # ------------------------------------------------------------------------------------------------
  # 질의문과 청크 임베딩 간의 코사인 유사도를 계산합니다
  # ================================================================================================
  async def _rank_dense_candidates(
    self,
    candidates: list[KnowledgeChunkCandidate],
    query: str,
    top_k: int,
  ) -> list[tuple[KnowledgeChunkCandidate, float]]:
    query_embedding = await self._embedding_service.embedding(query)
    if not query_embedding:
      raise ValueError("knowledge dense 검색용 query embedding 생성에 실패했습니다.")

    scored: list[tuple[KnowledgeChunkCandidate, float]] = []
    for candidate in candidates:
      if not candidate.embedding:
        continue
      score = self._cosine_similarity(query_embedding, candidate.embedding)
      scored.append((candidate, score))

    scored.sort(key=lambda item: (-item[1], item[0].chunk_index, item[0].display_name))
    return scored[:top_k]

  # ================================================================================================
  # 결과 결합
  # ------------------------------------------------------------------------------------------------
  # RRF 알고리즘을 활용해 희소 및 밀집 검색의 순위를 통합합니다
  # ================================================================================================
  def _fuse_ranked_results(
    self,
    sparse_ranked: list[tuple[KnowledgeChunkCandidate, float]],
    dense_ranked: list[tuple[KnowledgeChunkCandidate, float]],
    top_k: int,
  ) -> list[tuple[KnowledgeChunkCandidate, float]]:
    fused: dict[UUID, tuple[KnowledgeChunkCandidate, float]] = {}

    for rank, (candidate, _) in enumerate(sparse_ranked, start=1):
      current_score = fused.get(candidate.chunk_id, (candidate, 0.0))[1]
      fused[candidate.chunk_id] = (candidate, current_score + (1.0 / (_RRF_K + rank)))

    for rank, (candidate, _) in enumerate(dense_ranked, start=1):
      current_score = fused.get(candidate.chunk_id, (candidate, 0.0))[1]
      fused[candidate.chunk_id] = (candidate, current_score + (1.0 / (_RRF_K + rank)))

    ranked = sorted(
      fused.values(),
      key=lambda item: (-item[1], item[0].chunk_index, item[0].display_name),
    )
    return ranked[:top_k]

  # ================================================================================================
  # 결과 응답 구축
  # ------------------------------------------------------------------------------------------------
  # 최종 순위가 매겨진 결과를 직렬화 가능한 모델 형식으로 변환합니다
  # ================================================================================================
  def _build_result(
    self,
    knowledge_id: UUID,
    knowledge_title: str,
    search_mode: KnowledgeSearchMode,
    ranked: list[tuple[KnowledgeChunkCandidate, float]],
  ) -> KnowledgeSearchResult:
    return KnowledgeSearchResult(
      knowledge_id=knowledge_id,
      knowledge_title=knowledge_title,
      search_mode=search_mode,
      results=[
        KnowledgeSearchResultItem(
          chunk_id=candidate.chunk_id,
          source_id=candidate.source_id,
          display_name=candidate.display_name,
          chunk_index=candidate.chunk_index,
          content=candidate.content,
          score=round(score, 6),
          chunk_metadata=candidate.chunk_metadata,
        )
        for candidate, score in ranked
      ],
    )

  # ================================================================================================
  # 선택적 질의 정규화
  # ------------------------------------------------------------------------------------------------
  # 입력된 질의문의 공백을 제거하고 유효성을 검사하여 정규화합니다
  # ================================================================================================
  def _normalize_optional_query(self, query: str | None) -> str | None:
    if query is None:
      return None
    normalized_query = query.strip()
    if not normalized_query:
      return None
    return normalized_query

  # ================================================================================================
  # 토큰화
  # ------------------------------------------------------------------------------------------------
  # 희소 검색에 사용할 유효 토큰들을 텍스트에서 추출합니다
  # ================================================================================================
  def _tokenize(self, text: str) -> set[str]:
    return {token for token in _TOKEN_PATTERN.findall(text) if token}

  # ================================================================================================
  # 코사인 유사도 계산
  # ------------------------------------------------------------------------------------------------
  # 두 벡터 간의 유사도 점수를 산출합니다
  # ================================================================================================
  def _cosine_similarity(self, lhs: list[float], rhs: list[float]) -> float:
    if len(lhs) != len(rhs):
      logger.warning("임베딩 차원이 달라 dense 검색 점수를 0으로 처리합니다. lhs=%s rhs=%s", len(lhs), len(rhs))
      return 0.0

    numerator = sum(left * right for left, right in zip(lhs, rhs, strict=True))
    lhs_norm = math.sqrt(sum(value * value for value in lhs))
    rhs_norm = math.sqrt(sum(value * value for value in rhs))
    if lhs_norm == 0 or rhs_norm == 0:
      return 0.0
    return numerator / (lhs_norm * rhs_norm)
