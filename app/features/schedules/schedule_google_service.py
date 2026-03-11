import logging

from app.features.schedules.schedule_dto import ScheduleCreate
from app.features.schedules.schedule_dto import ScheduleUpdate
from app.infrastructure.google.calendar_client import GoogleCalendarClient

logger = logging.getLogger(__name__)


class ScheduleGoogleService:
  """구글 캘린더 원격 상태 동기화를 전담하는 서비스입니다."""

  def __init__(self, google_client: GoogleCalendarClient):
    self._google_client = google_client

  @property
  def is_connected(self) -> bool:
    """구글 연동 여부를 확인합니다."""
    return bool(self._google_client.access_token)

  async def create_event(self, calendar_id: str, payload: ScheduleCreate) -> str:
    """구글 캘린더에 일정을 생성하고 생성된 구글 이벤트 ID를 반환합니다."""
    event_data = {
      "summary": payload.summary,
      "description": payload.description,
      "start": {"dateTime": payload.start_at.isoformat()},
      "end": {"dateTime": payload.end_at.isoformat()},
    }
    if payload.color_id:
      event_data["colorId"] = payload.color_id

    result = await self._google_client.create_event(calendar_id, event_data)
    google_event_id = result.get("id")
    if not google_event_id:
      logger.error("Created event, but missing 'id' from Google API response.")
      raise ValueError("구글 일정 ID를 가져올 수 없습니다.")
    return google_event_id

  async def update_event(self, calendar_id: str, google_event_id: str, payload: ScheduleUpdate) -> None:
    """특정 구글 캘린더 일정을 수정합니다."""
    event_data = {}
    if payload.summary is not None:
      event_data["summary"] = payload.summary
    if payload.description is not None:
      event_data["description"] = payload.description
    if payload.start_at is not None:
      event_data["start"] = {"dateTime": payload.start_at.isoformat()}
    if payload.end_at is not None:
      event_data["end"] = {"dateTime": payload.end_at.isoformat()}
    if payload.color_id is not None:
      event_data["colorId"] = payload.color_id

    await self._google_client.update_event(calendar_id, google_event_id, event_data)

  async def delete_event(self, calendar_id: str, google_event_id: str) -> None:
    """구글 캘린더에서 일정을 삭제합니다."""
    await self._google_client.delete_event(calendar_id, google_event_id)
