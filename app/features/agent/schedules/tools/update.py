from datetime import datetime
from typing import Annotated

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.features.agent.entity import UpdateResultType
from app.features.schedules.schedule_dto import ScheduleUpdate
from app.features.schedules.schedule_service import ScheduleService


@tool
async def update_schedule(
  schedule_id: Annotated[int, "수정 대상 일정 ID (DB 식별자)"],
  summary: Annotated[str | None, "수정할 일정 제목"] = None,
  start_at: Annotated[str | None, "수정할 시작 일시"] = None,
  end_at: Annotated[str | None, "수정할 종료 일시"] = None,
  description: Annotated[str | None, "수정할 상세 설명"] = None,
  color_id: Annotated[str | None, "수정할 캘린더 색상 ID"] = None,
  *,
  config: RunnableConfig,
) -> str:
  """기존 파악된 ID의 일정을 캘린더에서 수정합니다."""
  configurable = config.get("configurable", {})
  user_id = configurable.get("user_id")

  if not user_id:
    return UpdateResultType.FAILED

  schedule_service: ScheduleService | None = configurable.get("schedule_service")
  if not schedule_service:
    return UpdateResultType.FAILED

  payload = ScheduleUpdate(
    summary=summary,
    description=description,
    start_at=datetime.fromisoformat(start_at) if start_at else None,
    end_at=datetime.fromisoformat(end_at) if end_at else None,
    color_id=color_id,
  )

  try:
    await schedule_service.update_schedule(
      owner_user_id=user_id,
      db_id=schedule_id,
      payload=payload,
    )
    return UpdateResultType.SUCCESS
  except ValueError:
    return UpdateResultType.NOT_FOUND
  except Exception:
    return UpdateResultType.FAILED
