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
from app.features.schedules.schedule_dto import ScheduleCreate
from app.features.schedules.schedule_dto import ScheduleSearchFilter
from app.features.schedules.schedule_dto import ScheduleUpdate
from app.infrastructure.models.event_embedding_model import EventEmbedding768Model
from app.infrastructure.models.event_embedding_model import EventEmbedding1024Model
from app.infrastructure.models.event_embedding_model import EventEmbedding1536Model
from app.infrastructure.models.event_embedding_model import EventEmbeddingBaseModel
from app.infrastructure.models.google_calendar_event_model import GoogleCalendarEventModel

logger = logging.getLogger(__name__)


class ScheduleDBService:
  """로컬 DB(`google_calendar_events`)만을 단일 원천(Source of Truth)으로 삼아 데이터를 투영/수정하는 저장소 전담 서비스입니다."""

  def __init__(self, session: Session):
    self._session = session
    self._dimension_to_model = {
      1024: EventEmbedding1024Model,
      1536: EventEmbedding1536Model,
      768: EventEmbedding768Model,
    }

  def create_schedule(
    self,
    owner_user_id: str,
    google_event_id: str | None,
    payload: ScheduleCreate,
    model_name: EmbeddingModelName | None = None,
    embedding: list[float] | None = None,
  ) -> GoogleCalendarEventModel:
    """일정을 DB에 반영합니다."""
    if model_name is not None and model_name not in AVAILABLE_EMBEDDING_MODELS:
      raise ValueError(f"Invalid embedding model name: {model_name}. Must be one of {AVAILABLE_EMBEDDING_MODELS}")
    if embedding is not None and model_name is None:
      raise ValueError("model_name is required when embedding is provided.")

    db_model = payload.to_model(
      owner_user_id=owner_user_id,
      google_event_id=google_event_id,
    )
    try:
      if embedding is not None:
        # 임베딩 정보 저장 루틴
        dimension = len(embedding)
        if model_name is None:
          raise ValueError("model_name is required when embedding is provided.")
        # 1. 베이스 모델 생성
        eb_base = EventEmbeddingBaseModel(
          model_name=model_name,
          dimension=dimension,
        )
        self._session.add(eb_base)
        self._session.flush()  # ID 확보

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
      logger.exception("Failed to create schedule in DB, rolling back transaction.")
      raise e

  def get_schedule(self, owner_user_id: str, id: int) -> GoogleCalendarEventModel | None:
    """단일 일정을 DB 식별자로 조회합니다."""
    query = select(GoogleCalendarEventModel).where(
      GoogleCalendarEventModel.id == id,
      GoogleCalendarEventModel.owner_user_id == owner_user_id,
      col(GoogleCalendarEventModel.deleted_at).is_(None),
    )
    return self._session.exec(query).first()

  def get_schedule_by_google_id(self, owner_user_id: str, google_event_id: str) -> GoogleCalendarEventModel | None:
    """단일 일정을 구글 이벤트 ID로 조회합니다."""
    query = select(GoogleCalendarEventModel).where(
      GoogleCalendarEventModel.google_event_id == google_event_id,
      GoogleCalendarEventModel.owner_user_id == owner_user_id,
      col(GoogleCalendarEventModel.deleted_at).is_(None),
    )
    return self._session.exec(query).first()

  def read_schedules(
    self,
    owner_user_id: str,
    filters: ScheduleSearchFilter,
    vector_threshold: float = 0.5,
  ) -> Sequence[GoogleCalendarEventModel]:
    """주어진 필터(기간, 키워드, 벡터)에 기반해 하이브리드 검색을 수행합니다."""
    query = select(GoogleCalendarEventModel).where(
      GoogleCalendarEventModel.owner_user_id == owner_user_id,
      col(GoogleCalendarEventModel.deleted_at).is_(None),  # 소프트 삭제 제외
    )

    # 1. 캘린더 ID 필터
    if filters.google_calendar_id:
      query = query.where(GoogleCalendarEventModel.google_calendar_id == filters.google_calendar_id)

    # 2. 기간 필터 (필수적/선택적)
    if filters.start_at:
      query = query.where(GoogleCalendarEventModel.end_at >= filters.start_at)
    if filters.end_at:
      query = query.where(GoogleCalendarEventModel.start_at <= filters.end_at)

    # 3. 키워드 & 임베딩 하이브리드 (OR 조건)
    keyword_cond = None
    vector_cond = None

    if filters.keyword:
      like_val = f"%{filters.keyword}%"
      keyword_cond = or_(
        col(GoogleCalendarEventModel.summary).ilike(like_val),
        col(GoogleCalendarEventModel.description).ilike(like_val),
      )

    if filters.query_vector:
      dimension = len(filters.query_vector)
      vec_model_cls = self._dimension_to_model.get(dimension)

      if vec_model_cls:
        # 해당 차원의 테이블과 조인하여 벡터 검색 수행
        query = query.join(vec_model_cls, GoogleCalendarEventModel.embedding_id == vec_model_cls.id)
        vector_cond = col(vec_model_cls.embedding).op("<=>")(filters.query_vector) < vector_threshold
      else:
        logger.warning(f"Unsupported query vector dimension: {dimension}")

    # 하이브리드 조건 병합
    if keyword_cond is not None and vector_cond is not None:
      query = query.where(or_(keyword_cond, vector_cond))
    elif keyword_cond is not None:
      query = query.where(keyword_cond)
    elif vector_cond is not None:
      query = query.where(vector_cond)

    if filters.limit is not None:
      query = query.limit(filters.limit)

    return self._session.exec(query).all()

  def update_schedule(
    self,
    db_model: GoogleCalendarEventModel,
    payload: ScheduleUpdate,
    model_name: EmbeddingModelName | None = None,
    updated_embedding: list[float] | None = None,
  ) -> GoogleCalendarEventModel:
    """기존 모델 인스턴스에 업데이트 요청 데이터를 덮어씌우고 커밋합니다."""
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
            # 기존 임베딩 업데이트
            vec_record = self._session.get(vec_model_cls, db_model.embedding_id)
            if vec_record:
              vec_record.embedding = updated_embedding
              self._session.add(vec_record)
            else:
              # 비정상 상황 시 신규 생성
              vec_record = vec_model_cls(id=db_model.embedding_id, embedding=updated_embedding)
              self._session.add(vec_record)
          else:
            # 신규 임베딩 생성 (Create 로직과 동일)
            if model_name is None:
              raise ValueError("model_name is required when updated_embedding is provided.")
            eb_base = EventEmbeddingBaseModel(model_name=model_name, dimension=dimension)
            self._session.add(eb_base)
            self._session.flush()
            vec_record = vec_model_cls(id=eb_base.id, embedding=updated_embedding)
            self._session.add(vec_record)
            db_model.embedding_id = eb_base.id
        else:
          logger.warning(f"Unsupported embedding dimension: {dimension}")

      db_model.updated_at = datetime.now(UTC)
      self._session.add(db_model)
      self._session.commit()
      self._session.refresh(db_model)
      return db_model
    except Exception as e:
      self._session.rollback()
      logger.exception("Failed to update schedule in DB, rolling back transaction.")
      raise e

  def delete_schedule(self, db_model: GoogleCalendarEventModel) -> None:
    """일정을 소프트 삭제합니다."""
    try:
      db_model.deleted_at = datetime.now(UTC)
      db_model.updated_at = datetime.now(UTC)
      self._session.add(db_model)
      self._session.commit()
    except Exception as e:
      self._session.rollback()
      logger.exception("Failed to delete schedule in DB, rolling back transaction.")
      raise e
