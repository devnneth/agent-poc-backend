from __future__ import annotations

import asyncio
from typing import Protocol

from sqlmodel import Session
from sqlmodel import col
from sqlmodel import delete

from app.core.config.environment import settings
from app.features.knowledge.common.knowledge_entity import DocumentChunk
from app.infrastructure.models.knowledge_model import KnowledgeChunksModel
from app.infrastructure.models.knowledge_model import KnowledgeSourcesModel


# ==================================================================================================
# 청크 임베딩 게이트웨이 인터페이스
# --------------------------------------------------------------------------------------------------
# 청크 본문을 벡터로 변환하는 임베딩 서비스의 최소 계약을 정의합니다
# ==================================================================================================
class ChunkEmbeddingGateway(Protocol):
  # ================================================================================================
  # 텍스트 임베딩
  # ------------------------------------------------------------------------------------------------
  # 전달된 청크 본문 목록을 같은 순서의 벡터 목록으로 변환합니다
  # ================================================================================================
  async def embedding(self, texts: list[str]) -> list[list[float]]: ...


# ==================================================================================================
# 청크 영속화 서비스
# --------------------------------------------------------------------------------------------------
# 청킹 이후 단계인 임베딩 생성과 knowledge_chunks 교체 저장을 공통으로 담당합니다
# ==================================================================================================
class KnowledgeChunkPersistenceService:
  # ================================================================================================
  # 초기화
  # ------------------------------------------------------------------------------------------------
  # 공통 임베딩 서비스와 배치 크기를 주입받아 청크 저장 준비를 합니다
  # ================================================================================================
  def __init__(
    self,
    embedding_service: ChunkEmbeddingGateway,
    embedding_batch_size: int | None = None,
  ):
    self._embedding_service = embedding_service
    self._embedding_batch_size = embedding_batch_size or settings.RAG_EMBEDDING_BATCH_SIZE

  # ================================================================================================
  # 청크 임베딩 후 교체 저장
  # ------------------------------------------------------------------------------------------------
  # 생성된 청크 목록을 임베딩한 뒤 기존 청크를 지우고 새 청크로 교체합니다
  # ================================================================================================
  def embed_and_replace_chunks(
    self,
    session: Session,
    source: KnowledgeSourcesModel,
    chunks: list[DocumentChunk],
  ) -> int:
    embeddings = self.embed_chunks([chunk.content for chunk in chunks])
    if len(chunks) != len(embeddings):
      raise ValueError("청크 수와 임베딩 수가 일치하지 않습니다.")

    self.replace_chunks(session, source, chunks, embeddings)
    return sum(len(chunk.content.split()) for chunk in chunks)

  # ================================================================================================
  # 청크 임베딩 생성
  # ------------------------------------------------------------------------------------------------
  # 배치 단위로 청크 본문을 임베딩해 전체 벡터 목록을 반환합니다
  # ================================================================================================
  def embed_chunks(self, chunk_texts: list[str]) -> list[list[float]]:
    embeddings: list[list[float]] = []

    for start in range(0, len(chunk_texts), self._embedding_batch_size):
      batch = chunk_texts[start : start + self._embedding_batch_size]
      batch_embeddings = asyncio.run(self._embedding_service.embedding(batch))
      if len(batch_embeddings) != len(batch):
        raise ValueError("배치 임베딩 결과 수가 요청 수와 다릅니다.")
      embeddings.extend(batch_embeddings)

    return embeddings

  # ================================================================================================
  # 청크 교체 저장
  # ------------------------------------------------------------------------------------------------
  # 같은 source의 기존 청크를 삭제한 뒤 새 청크와 임베딩을 저장합니다
  # ================================================================================================
  def replace_chunks(
    self,
    session: Session,
    source: KnowledgeSourcesModel,
    chunks: list[DocumentChunk],
    embeddings: list[list[float]],
  ) -> None:
    session.exec(delete(KnowledgeChunksModel).where(col(KnowledgeChunksModel.source_id) == source.id))

    for chunk, embedding in zip(chunks, embeddings, strict=True):
      session.add(
        KnowledgeChunksModel(
          source_id=source.id,
          user_id=source.user_id,
          chunk_index=chunk.chunk_index,
          chunk_content=chunk.content,
          embedding=embedding,
          chunk_metadata=chunk.metadata_payload(),
        )
      )
