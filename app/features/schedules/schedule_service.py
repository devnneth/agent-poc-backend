import logging
from collections.abc import Sequence
from typing import Any

from app.features.llm.embedding_service import EmbeddingService
from app.features.schedules.schedule_db_service import ScheduleDBService
from app.features.schedules.schedule_dto import ScheduleCreate
from app.features.schedules.schedule_dto import ScheduleSearchFilter
from app.features.schedules.schedule_dto import ScheduleUpdate
from app.features.schedules.schedule_google_service import ScheduleGoogleService
from app.infrastructure.models.google_calendar_event_model import GoogleCalendarEventModel

logger = logging.getLogger(__name__)


class ScheduleService:
  """ScheduleDBService와 ScheduleGoogleService를 통합(Facade)하여 양쪽 상태 동기화를 담당합니다."""

  def __init__(
    self,
    db_service: ScheduleDBService,
    google_service: ScheduleGoogleService,
    embedding_service: EmbeddingService | None = None,
  ):
    self._db_service = db_service
    self._google_service = google_service
    self._embedding_service = embedding_service

  async def create_schedule(
    self,
    owner_user_id: str,
    payload: ScheduleCreate,
  ) -> GoogleCalendarEventModel:
    """1. 구글 캘린더에 일정 생성 -> 2. 결과 ID를 기반으로 로컬 DB에 등록"""
    google_event_id: str | None = None
    is_google_connected = self._google_service.is_connected

    if is_google_connected and payload.google_calendar_id:
      google_event_id = await self._google_service.create_event(
        calendar_id=payload.google_calendar_id,
        payload=payload,
      )
    else:
      logger.info(
        f"구글 캘린더가 연결이 안되었거나 캘린더 아이디가 없습니다. 로컬 DB에만 저장합니다. {payload.google_calendar_id}, {self._google_service.is_connected}"
      )

    # 2. 임베딩 생성 (비동기 호출)
    embedding = None
    if self._embedding_service:
      text_to_embed = ScheduleService.format_schedule_for_embedding(
        summary=payload.summary,
        description=payload.description,
        start_at=payload.start_at,
        end_at=payload.end_at,
      )
      if text_to_embed:
        embedding = await self._embedding_service.embedding(text_to_embed)

    try:
      # 3. 결과 ID와 임베딩을 기반으로 로컬 DB에 등록
      return self._db_service.create_schedule(
        owner_user_id=owner_user_id,
        google_event_id=google_event_id,
        payload=payload,
        model_name=self._embedding_service.model_name if self._embedding_service else None,
        embedding=embedding,
      )
    except Exception as e:
      # DB 삽입 실패 시 보상 트랜잭션(구글 이벤트 롤백 삭제)를 강제할 수도 있습니다.
      if google_event_id and payload.google_calendar_id:
        logger.error("Failed to insert schedule in local DB, rolling back Google Event... %s", str(e))
        try:
          await self._google_service.delete_event(payload.google_calendar_id, google_event_id)
        except Exception as rollback_e:
          logger.error("Rollback failed! Orphaned event exists: %s", str(rollback_e))
      raise e

  def read_schedules(
    self,
    owner_user_id: str,
    filters: ScheduleSearchFilter,
  ) -> Sequence[GoogleCalendarEventModel]:
    """조회 기능은 Single Source of Truth 원칙에 따라 DB에서만 가져옵니다."""
    return self._db_service.read_schedules(owner_user_id=owner_user_id, filters=filters)

  async def update_schedule(
    self,
    owner_user_id: str,
    db_id: int,
    payload: ScheduleUpdate,
    updated_embedding: list[float] | None = None,
  ) -> GoogleCalendarEventModel:
    """일정을 갱신합니다."""
    # 1. 대상 데이터베이스 모델 확인
    db_model = self._db_service.get_schedule(owner_user_id, db_id)
    if not db_model:
      raise ValueError("해당 일정을 찾을 수 없거나 접근 권한이 없습니다.")

    # 2. 구글 캘린더 원격 갱신
    is_google_connected = self._google_service.is_connected
    if is_google_connected and db_model.google_event_id and db_model.google_calendar_id:
      await self._google_service.update_event(
        calendar_id=db_model.google_calendar_id,
        google_event_id=db_model.google_event_id,
        payload=payload,
      )
    elif not is_google_connected:
      logger.info(f"구글 캘린더가 연결이 안되었거나 캘린더 아이디가 없습니다. 로컬 DB에만 저장합니다. {db_model.google_calendar_id}, {is_google_connected}")
    # 3. 로컬 DB 갱신
    # 내용이 변경되었을 경우 임베딩 재생성
    if self._embedding_service and (
      payload.summary is not None or payload.description is not None or payload.start_at is not None or payload.end_at is not None
    ):
      # 현재 데이터와 업데이트 내용을 결합하여 새로운 텍스트 생성
      new_summary = payload.summary if payload.summary is not None else (db_model.summary or "")
      new_description = payload.description if payload.description is not None else (db_model.description or "")
      new_start = payload.start_at if payload.start_at is not None else db_model.start_at
      new_end = payload.end_at if payload.end_at is not None else db_model.end_at

      text_to_embed = ScheduleService.format_schedule_for_embedding(
        summary=new_summary,
        description=new_description,
        start_at=new_start,
        end_at=new_end,
      )
      if text_to_embed:
        updated_embedding = await self._embedding_service.embedding(text_to_embed)

    return self._db_service.update_schedule(
      db_model,
      payload,
      model_name=self._embedding_service.model_name if self._embedding_service else None,
      updated_embedding=updated_embedding,
    )

  @staticmethod
  def format_schedule_for_embedding(
    summary: str | None,
    description: str | None,
    start_at: Any,
    end_at: Any,
  ) -> str:
    """임베딩을 위한 텍스트 포맷팅을 수행합니다."""
    return (f"제목 : {summary or ''}\n설명 : {description or ''}\n시작시간 : {start_at}\n종료시간 : {end_at}").strip()

  async def delete_schedule(self, owner_user_id: str, db_id: int) -> None:
    """일정을 삭제합니다."""
    db_model = self._db_service.get_schedule(owner_user_id, db_id)
    if not db_model:
      raise ValueError("해당 일정을 찾을 수 없거나 접근 권한이 없습니다.")

    # 1. 구글 캘린더 원격 삭제
    is_google_connected = self._google_service.is_connected
    if is_google_connected and db_model.google_event_id and db_model.google_calendar_id:
      await self._google_service.delete_event(
        calendar_id=db_model.google_calendar_id,
        google_event_id=db_model.google_event_id,
      )
    elif not is_google_connected:
      logger.info(f"구글 캘린더가 연결이 안되었거나 캘린더 아이디가 없습니다. 로컬 DB에만 저장합니다. {db_model.google_calendar_id}, {is_google_connected}")

    # 2. 로컬 DB 소프트 삭제 반영
    self._db_service.delete_schedule(db_model)
