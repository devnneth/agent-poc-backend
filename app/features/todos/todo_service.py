import logging
from collections.abc import Sequence
from typing import Any

from app.features.llm.embedding_service import EmbeddingService
from app.features.todos.todo_db_service import TodoDBService
from app.features.todos.todo_dto import TodoCreate
from app.features.todos.todo_dto import TodoSearchFilter
from app.features.todos.todo_dto import TodoUpdate
from app.infrastructure.models.todo_model import TodoModel

logger = logging.getLogger(__name__)


class TodoService:
  """TodoDBService와 EmbeddingService를 통합하여 할일 관리 및 임베딩 동기화를 담당합니다."""

  def __init__(
    self,
    db_service: TodoDBService,
    embedding_service: EmbeddingService | None = None,
  ):
    self._db_service = db_service
    self._embedding_service = embedding_service

  async def create_todo(
    self,
    owner_user_id: str,
    payload: TodoCreate,
  ) -> TodoModel:
    """임베딩을 생성하고 할일을 DB에 저장합니다."""
    embedding = None
    if self._embedding_service:
      text_to_embed = self.format_todo_for_embedding(
        title=payload.title,
        description=payload.description,
        status=payload.status,
        priority=payload.priority,
        project=payload.project,
      )
      if text_to_embed:
        embedding = await self._embedding_service.embedding(text_to_embed)

    return self._db_service.create_todo(
      owner_user_id=owner_user_id,
      payload=payload,
      model_name=self._embedding_service.model_name if self._embedding_service else None,
      embedding=embedding,
    )

  def read_todos(
    self,
    owner_user_id: str,
    filters: TodoSearchFilter,
  ) -> Sequence[TodoModel]:
    """할일 목록을 조회합니다."""
    return self._db_service.read_todos(owner_user_id=owner_user_id, filters=filters)

  async def update_todo(
    self,
    owner_user_id: str,
    db_id: int,
    payload: TodoUpdate,
  ) -> TodoModel:
    """할일을 수정하고 필요시 임베딩을 재생성합니다."""
    db_model = self._db_service.get_todo(owner_user_id, db_id)
    if not db_model:
      raise ValueError("해당 할일을 찾을 수 없거나 접근 권한이 없습니다.")

    updated_embedding = None
    if self._embedding_service and (
      payload.title is not None or payload.description is not None or payload.status is not None or payload.priority is not None or payload.project is not None
    ):
      new_title = payload.title if payload.title is not None else db_model.title
      new_desc = payload.description if payload.description is not None else db_model.description
      new_status = payload.status if payload.status is not None else db_model.status
      new_priority = payload.priority if payload.priority is not None else db_model.priority
      new_project = payload.project if payload.project is not None else db_model.project

      text_to_embed = self.format_todo_for_embedding(
        title=new_title,
        description=new_desc,
        status=new_status,
        priority=new_priority,
        project=new_project,
      )
      if text_to_embed:
        updated_embedding = await self._embedding_service.embedding(text_to_embed)

    return self._db_service.update_todo(
      db_model,
      payload,
      model_name=self._embedding_service.model_name if self._embedding_service else None,
      updated_embedding=updated_embedding,
    )

  def delete_todo(self, owner_user_id: str, db_id: int) -> None:
    """할일을 삭제합니다."""
    db_model = self._db_service.get_todo(owner_user_id, db_id)
    if not db_model:
      raise ValueError("해당 할일을 찾을 수 없거나 접근 권한이 없습니다.")
    self._db_service.delete_todo(db_model)

  @staticmethod
  def format_todo_for_embedding(
    title: str,
    description: str,
    status: Any,
    priority: Any,
    project: str,
  ) -> str:
    """임베딩을 위한 텍스트 포맷팅을 수행합니다."""
    return f"제목 : {title}\n설명 : {description}\n상태 : {status}\n우선순위 : {priority}\n프로젝트 : {project}".strip()
