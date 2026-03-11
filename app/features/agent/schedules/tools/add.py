from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Annotated

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.features.schedules.schedule_dto import ScheduleCreate
from app.features.schedules.schedule_service import ScheduleService


@tool
async def add_schedule(
  summary: Annotated[str, "일정 제목"],
  start_at: Annotated[str, "시작 일시 (ISO 8601 형식 문자열)"],
  end_at: Annotated[str, "종료 일시 (ISO 8601 형식 문자열)"],
  description: Annotated[str | None, "상세 설명"] = None,
  color_id: Annotated[str | None, "구글 캘린더 색상 ID"] = None,
  *,
  config: RunnableConfig,
) -> str:
  """새로운 일정을 캘린더에 추가합니다."""
  configurable = config.get("configurable", {})
  user_id = configurable.get("user_id")
  calendar_id = configurable.get("calendar_id")

  if not user_id:
    return "오류: 사용자 정보(user_id)를 찾을 수 없습니다."

  try:
    # ISO 8601 문자열을 파싱 (Z 또는 +HH:MM 형식 대응)
    dt_start = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
    dt_end = datetime.fromisoformat(end_at.replace("Z", "+00:00"))

    # 타임존 정보가 없는 경우 (naive datetime), minutes_offset을 사용하여 타임존 설정
    if dt_start.tzinfo is None:
      minutes_offset = configurable.get("minutes_offset", 540)
      tz = timezone(timedelta(minutes=minutes_offset))
      dt_start = dt_start.replace(tzinfo=tz)
      dt_end = dt_end.replace(tzinfo=tz)

    payload = ScheduleCreate(
      google_calendar_id=calendar_id,
      summary=summary,
      start_at=dt_start,
      end_at=dt_end,
      description=description,
      color_id=color_id,
    )

    schedule_service: ScheduleService | None = configurable.get("schedule_service")
    if not schedule_service:
      return "오류: 시스템 설정에서 일정 서비스(schedule_service) 인스턴스를 찾을 수 없습니다."

    result_model = await schedule_service.create_schedule(owner_user_id=user_id, payload=payload)

    return f"'{summary}' 일정이 {start_at} 시간에 생성되었습니다. (ID: {result_model.id})"
  except Exception as e:
    return f"일정 생성 실패: {e!s}"
