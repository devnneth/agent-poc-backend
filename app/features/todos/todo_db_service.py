import logging
from collections.abc import Sequence
from datetime import UTC
from datetime import datetime

from sqlalchemy import or_
from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from app.features.agent.settings import AVAILABLE_EMBEDDING_MODELS
from app.features.agent.settings import EmbeddingModelName
from app.features.todos.todo_dto import TodoCreate
from app.features.todos.todo_dto import TodoSearchFilter
from app.features.todos.todo_dto import TodoUpdate
from app.infrastructure.models.event_embedding_model import EventEmbedding768Model
from app.infrastructure.models.event_embedding_model import EventEmbedding1024Model
from app.infrastructure.models.event_embedding_model import EventEmbedding1536Model
from app.infrastructure.models.event_embedding_model import EventEmbeddingBaseModel
from app.infrastructure.models.todo_model import TodoModel

logger = logging.getLogger(__name__)


class TodoDBService:
  """로컬 DB(`todos`)를 관리하며 임베딩 동기화를 수행하는 저장소 전담 서비스입니다."""

  def __init__(self, session: Session):
    self._session = session
    self._dimension_to_model = {
      1024: EventEmbedding1024Model,
      1536: EventEmbedding1536Model,
      768: EventEmbedding768Model,
    }

  def create_todo(
    self,
    owner_user_id: str,
    payload: TodoCreate,
    model_name: EmbeddingModelName | None = None,
    embedding: list[float] | None = None,
  ) -> TodoModel:
    """할일을 DB에 반영하고 임베딩을 저장합니다."""
    if model_name is not None and model_name not in AVAILABLE_EMBEDDING_MODELS:
      raise ValueError(f"Invalid embedding model name: {model_name}. Must be one of {AVAILABLE_EMBEDDING_MODELS}")
    if embedding is not None and model_name is None:
      raise ValueError("model_name is required when embedding is provided.")

    db_model = payload.to_model(owner_user_id=owner_user_id)
    try:
      if embedding is not None:
        dimension = len(embedding)
        if model_name is None:
          raise ValueError("model_name is required when embedding is provided.")
        # 1. 베이스 모델 생성
        eb_base = EventEmbeddingBaseModel(
          model_name=model_name,
          dimension=dimension,
        )
        self._session.add(eb_base)
        self._session.flush()

        # 2. 전용 벡터 테이블 저장
        vec_model_cls = self._dimension_to_model.get(dimension)
        if vec_model_cls:
          vec_record = vec_model_cls(id=eb_base.id, embedding=embedding)
          self._session.add(vec_record)
          db_model.embedding_id = eb_base.id
        else:
          logger.warning(f"Unsupported embedding dimension: {dimension}")

      self._session.add(db_model)
      self._session.commit()
      self._session.refresh(db_model)
      return db_model
    except Exception as e:
      self._session.rollback()
      logger.exception("Failed to create todo in DB, rolling back transaction.")
      raise e

  def get_todo(self, owner_user_id: str, id: int) -> TodoModel | None:
    """단일 할일을 ID로 조회합니다."""
    query = select(TodoModel).where(
      TodoModel.id == id,
      TodoModel.owner_user_id == owner_user_id,
      col(TodoModel.deleted_at).is_(None),
    )
    return self._session.exec(query).first()

  def read_todos(
    self,
    owner_user_id: str,
    filters: TodoSearchFilter,
    vector_threshold: float = 0.5,
  ) -> Sequence[TodoModel]:
    """필터와 벡터를 기반으로 할일을 조회합니다."""
    query = select(TodoModel).where(
      TodoModel.owner_user_id == owner_user_id,
      col(TodoModel.deleted_at).is_(None),
    )

    if filters.status:
      query = query.where(TodoModel.status == filters.status)
    if filters.priority:
      query = query.where(TodoModel.priority == filters.priority)
    if filters.project:
      query = query.where(TodoModel.project == filters.project)

    keyword_cond = None
    vector_cond = None

    if filters.keyword:
      like_val = f"%{filters.keyword}%"
      keyword_cond = or_(
        col(TodoModel.title).ilike(like_val),
        col(TodoModel.description).ilike(like_val),
      )

    if filters.query_vector:
      dimension = len(filters.query_vector)
      vec_model_cls = self._dimension_to_model.get(dimension)
      if vec_model_cls:
        query = query.join(vec_model_cls, TodoModel.embedding_id == vec_model_cls.id)
        vector_cond = col(vec_model_cls.embedding).op("<=>")(filters.query_vector) < vector_threshold

    if keyword_cond is not None and vector_cond is not None:
      query = query.where(or_(keyword_cond, vector_cond))
    elif keyword_cond is not None:
      query = query.where(keyword_cond)
    elif vector_cond is not None:
      query = query.where(vector_cond)

    # 정렬 및 개수 제한 적용
    query = query.order_by(col(TodoModel.created_at).desc())
    if filters.limit:
      query = query.limit(filters.limit)

    return self._session.exec(query).all()

  def update_todo(
    self,
    db_model: TodoModel,
    payload: TodoUpdate,
    model_name: EmbeddingModelName | None = None,
    updated_embedding: list[float] | None = None,
  ) -> TodoModel:
    """기존 할일을 업데이트하고 임베딩을 갱신합니다."""
    if model_name is not None and model_name not in AVAILABLE_EMBEDDING_MODELS:
      raise ValueError(f"Invalid embedding model name: {model_name}. Must be one of {AVAILABLE_EMBEDDING_MODELS}")
    if updated_embedding is not None and model_name is None:
      raise ValueError("model_name is required when updated_embedding is provided.")

    try:
      update_data = payload.model_dump(exclude_unset=True)
      for key, value in update_data.items():
        setattr(db_model, key, value)

      if updated_embedding is not None:
        dimension = len(updated_embedding)
        vec_model_cls = self._dimension_to_model.get(dimension)
        if vec_model_cls:
          if db_model.embedding_id:
            vec_record = self._session.get(vec_model_cls, db_model.embedding_id)
            if vec_record:
              vec_record.embedding = updated_embedding
              self._session.add(vec_record)
            else:
              vec_record = vec_model_cls(id=db_model.embedding_id, embedding=updated_embedding)
              self._session.add(vec_record)
          else:
            if model_name is None:
              raise ValueError("model_name is required when updated_embedding is provided.")
            eb_base = EventEmbeddingBaseModel(model_name=model_name, dimension=dimension)
            self._session.add(eb_base)
            self._session.flush()
            vec_record = vec_model_cls(id=eb_base.id, embedding=updated_embedding)
            self._session.add(vec_record)
            db_model.embedding_id = eb_base.id

      db_model.updated_at = datetime.now(UTC)
      self._session.add(db_model)
      self._session.commit()
      self._session.refresh(db_model)
      return db_model
    except Exception as e:
      self._session.rollback()
      logger.exception("Failed to update todo in DB, rolling back transaction.")
      raise e

  def delete_todo(self, db_model: TodoModel) -> None:
    """할일을 소프트 삭제합니다."""
    try:
      db_model.deleted_at = datetime.now(UTC)
      db_model.updated_at = datetime.now(UTC)
      self._session.add(db_model)
      self._session.commit()
    except Exception as e:
      self._session.rollback()
      logger.exception("Failed to delete todo in DB, rolling back transaction.")
      raise e
