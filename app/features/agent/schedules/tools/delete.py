from typing import Annotated

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.features.agent.entity import DeleteResultType
from app.features.schedules.schedule_service import ScheduleService


@tool
async def delete_schedule(
  schedule_id: Annotated[int, "삭제 대상 일정 ID (DB 식별자)"],
  *,
  config: RunnableConfig,
) -> str:
  """지정된 ID의 일정을 삭제합니다."""
  configurable = config.get("configurable", {})
  user_id = configurable.get("user_id")

  if not user_id:
    return DeleteResultType.FAILED

  schedule_service: ScheduleService | None = configurable.get("schedule_service")
  if not schedule_service:
    return DeleteResultType.FAILED

  try:
    await schedule_service.delete_schedule(owner_user_id=user_id, db_id=schedule_id)
    return DeleteResultType.SUCCESS
  except ValueError:
    return DeleteResultType.NOT_FOUND
  except Exception:
    return DeleteResultType.FAILED
