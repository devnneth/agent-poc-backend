import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class GoogleCalendarClientError(Exception):
  def __init__(self, message: str, status_code: int = 500):
    super().__init__(message)
    self.status_code = status_code


class GoogleCalendarClient:
  """Google Calendar API 연동을 전담하는 인프라 클라이언트입니다."""

  def __init__(self, access_token: str | None):
    self.access_token = access_token
    self.base_url = "https://www.googleapis.com/calendar/v3"

  def _get_headers(self) -> dict[str, str]:
    if not self.access_token:
      return {"Content-Type": "application/json"}
    return {
      "Authorization": f"Bearer {self.access_token}",
      "Content-Type": "application/json",
    }

  async def create_event(self, calendar_id: str, event_data: dict[str, Any]) -> dict[str, Any]:
    """Google Calendar에 이벤트를 생성합니다."""
    url = f"{self.base_url}/calendars/{calendar_id}/events"
    try:
      async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=self._get_headers(), json=event_data)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
      logger.error("Failed to create Google Calendar event: %s", e.response.text)
      raise GoogleCalendarClientError(
        f"구글 일정 등록에 실패했습니다: {e.response.text}",
        status_code=e.response.status_code,
      ) from e
    except Exception as e:
      logger.exception("Unexpected error while creating Google Calendar event")
      raise GoogleCalendarClientError("구글 일정 등록 중 오류가 발생했습니다.") from e

  async def update_event(self, calendar_id: str, event_id: str, event_data: dict[str, Any]) -> dict[str, Any]:
    """Google Calendar의 기존 이벤트를 수정합니다."""
    url = f"{self.base_url}/calendars/{calendar_id}/events/{event_id}"
    try:
      async with httpx.AsyncClient() as client:
        response = await client.put(url, headers=self._get_headers(), json=event_data)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
      logger.error("Failed to update Google Calendar event: %s", e.response.text)
      raise GoogleCalendarClientError(
        f"구글 일정 수정에 실패했습니다: {e.response.text}",
        status_code=e.response.status_code,
      ) from e
    except Exception as e:
      logger.exception("Unexpected error while updating Google Calendar event")
      raise GoogleCalendarClientError("구글 일정 수정 중 오류가 발생했습니다.") from e

  async def delete_event(self, calendar_id: str, event_id: str) -> None:
    """Google Calendar의 기존 이벤트를 삭제합니다."""
    url = f"{self.base_url}/calendars/{calendar_id}/events/{event_id}"
    try:
      async with httpx.AsyncClient() as client:
        response = await client.delete(url, headers=self._get_headers())
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
      if e.response.status_code == 404:
        return  # Base case: Already deleted
      logger.error("Failed to delete Google Calendar event: %s", e.response.text)
      raise GoogleCalendarClientError(
        f"구글 일정 삭제에 실패했습니다: {e.response.text}",
        status_code=e.response.status_code,
      ) from e
    except Exception as e:
      logger.exception("Unexpected error while deleting Google Calendar event")
      raise GoogleCalendarClientError("구글 일정 삭제 중 오류가 발생했습니다.") from e
