from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from app.features.knowledge.common.chunk_persistence_service import KnowledgeChunkPersistenceService
from app.features.knowledge.common.knowledge_entity import ChunkMetadata
from app.features.knowledge.common.knowledge_entity import DocumentChunk
from app.infrastructure.models.knowledge_model import KnowledgeSourcesModel
from app.infrastructure.models.knowledge_model import ProcessingStatus
from app.infrastructure.models.knowledge_model import SourceType


# ==================================================================================================
# 모의 임베딩 서비스
# --------------------------------------------------------------------------------------------------
# 요청된 배치 목록을 기록하며 고정 벡터를 반환하는 테스트용 서비스입니다
# ==================================================================================================
class RecordingEmbeddingService:
  # ================================================================================================
  # 초기화
  # ------------------------------------------------------------------------------------------------
  # 호출된 배치 내역을 확인할 수 있도록 저장소를 준비합니다
  # ================================================================================================
  def __init__(self):
    self.batches: list[list[str]] = []

  # ================================================================================================
  # 임베딩 생성
  # ------------------------------------------------------------------------------------------------
  # 입력된 텍스트 배치를 기록하고 같은 길이의 더미 벡터 목록을 반환합니다
  # ================================================================================================
  async def embedding(self, texts: list[str]) -> list[list[float]]:
    self.batches.append(texts)
    return [[0.1] * 1536 for _ in texts]


# ==================================================================================================
# 임베딩 배치 분할 테스트
# --------------------------------------------------------------------------------------------------
# 공통 서비스가 설정된 배치 크기대로 청크 임베딩 요청을 분할하는지 검증합니다
# ==================================================================================================
def test_chunk_persistence_service_batches_embeddings():
  embedding_service = RecordingEmbeddingService()
  service = KnowledgeChunkPersistenceService(
    embedding_service=embedding_service,
    embedding_batch_size=2,
  )

  embeddings = service.embed_chunks(["첫 번째", "두 번째", "세 번째"])

  assert len(embeddings) == 3
  assert embedding_service.batches == [["첫 번째", "두 번째"], ["세 번째"]]


# ==================================================================================================
# 임베딩 후 청크 교체 저장 테스트
# --------------------------------------------------------------------------------------------------
# 공통 서비스가 기존 청크 삭제 후 새 청크를 저장하고 토큰 수를 반환하는지 검증합니다
# ==================================================================================================
def test_chunk_persistence_service_embeds_and_replaces_chunks():
  embedding_service = RecordingEmbeddingService()
  service = KnowledgeChunkPersistenceService(
    embedding_service=embedding_service,
    embedding_batch_size=2,
  )
  source = KnowledgeSourcesModel(
    id=uuid4(),
    knowledge_id=uuid4(),
    user_id="user-123",
    source_type=SourceType.FILE,
    display_name="doc.pdf",
    storage_path="user-123/doc.pdf",
    processing_status=ProcessingStatus.ING,
  )
  chunks = [
    DocumentChunk(
      chunk_index=0,
      content="첫 번째 청크 본문",
      metadata=ChunkMetadata(heading_path=["문서"], content_type="section"),
    ),
    DocumentChunk(
      chunk_index=1,
      content="두 번째 청크 본문",
      metadata={
        "title": "세부",
        "navigation": "문서 > 세부",
        "chunking_strategy": "hybrid",
      },
    ),
  ]
  session = MagicMock()

  token_count = service.embed_and_replace_chunks(session, source, chunks)

  assert token_count == 8
  assert len(embedding_service.batches) == 1
  assert session.exec.call_count == 1
  assert session.add.call_count == 2

  first_saved_chunk = session.add.call_args_list[0].args[0]
  second_saved_chunk = session.add.call_args_list[1].args[0]
  assert first_saved_chunk.source_id == source.id
  assert first_saved_chunk.chunk_index == 0
  assert first_saved_chunk.chunk_content == "첫 번째 청크 본문"
  assert first_saved_chunk.chunk_metadata == {"heading_path": ["문서"], "page_range": None, "content_type": "section"}
  assert second_saved_chunk.chunk_index == 1
  assert second_saved_chunk.chunk_metadata == {
    "title": "세부",
    "navigation": "문서 > 세부",
    "chunking_strategy": "hybrid",
  }
