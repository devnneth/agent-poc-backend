import logging
from collections.abc import Sequence

from app.features.llm.embedding_service import EmbeddingService
from app.features.memos.memo_db_service import MemoDBService
from app.features.memos.memo_dto import MemoCreate
from app.features.memos.memo_dto import MemoSearchFilter
from app.features.memos.memo_dto import MemoUpdate
from app.infrastructure.models.memo_model import MemoModel

logger = logging.getLogger(__name__)


class MemoService:
  """MemoDBService와 EmbeddingService를 통합하여 메모 관리 및 임베딩 동기화를 담당합니다."""

  def __init__(
    self,
    db_service: MemoDBService,
    embedding_service: EmbeddingService | None = None,
  ):
    self._db_service = db_service
    self._embedding_service = embedding_service

  async def create_memo(
    self,
    owner_user_id: str,
    payload: MemoCreate,
  ) -> MemoModel:
    """임베딩을 생성하고 메모를 DB에 저장합니다."""
    embedding = None
    if self._embedding_service:
      text_to_embed = self.format_memo_for_embedding(
        title=payload.title,
        content=payload.content,
      )
      if text_to_embed:
        embedding = await self._embedding_service.embedding(text_to_embed)

    return self._db_service.create_memo(
      owner_user_id=owner_user_id,
      payload=payload,
      model_name=self._embedding_service.model_name if self._embedding_service else None,
      embedding=embedding,
    )

  def read_memos(
    self,
    owner_user_id: str,
    filters: MemoSearchFilter,
  ) -> Sequence[MemoModel]:
    """메모 목록을 조회합니다."""
    return self._db_service.read_memos(owner_user_id=owner_user_id, filters=filters)

  async def update_memo(
    self,
    owner_user_id: str,
    db_id: int,
    payload: MemoUpdate,
  ) -> MemoModel:
    """메모를 수정하고 필요시 임베딩을 재생성합니다."""
    db_model = self._db_service.get_memo(owner_user_id, db_id)
    if not db_model:
      raise ValueError("해당 메모를 찾을 수 없거나 접근 권한이 없습니다.")

    updated_embedding = None
    if self._embedding_service and (payload.title is not None or payload.content is not None):
      new_title = payload.title if payload.title is not None else db_model.title
      new_content = payload.content if payload.content is not None else db_model.content

      text_to_embed = self.format_memo_for_embedding(
        title=new_title,
        content=new_content,
      )
      if text_to_embed:
        updated_embedding = await self._embedding_service.embedding(text_to_embed)

    return self._db_service.update_memo(
      db_model,
      payload,
      model_name=self._embedding_service.model_name if self._embedding_service else None,
      updated_embedding=updated_embedding,
    )

  def delete_memo(self, owner_user_id: str, db_id: int) -> None:
    """메모를 삭제합니다."""
    db_model = self._db_service.get_memo(owner_user_id, db_id)
    if not db_model:
      raise ValueError("해당 메모를 찾을 수 없거나 접근 권한이 없습니다.")
    self._db_service.delete_memo(db_model)

  @staticmethod
  def format_memo_for_embedding(
    title: str,
    content: str,
  ) -> str:
    """임베딩을 위한 텍스트 포맷팅을 수행합니다."""
    return f"제목 : {title}\n내용 : {content}".strip()
