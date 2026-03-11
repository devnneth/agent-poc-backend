import json
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Annotated

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.features.schedules.schedule_dto import ScheduleSearchFilter
from app.features.schedules.schedule_service import ScheduleService
from app.infrastructure.models.google_calendar_event_model import GoogleCalendarEventModel


@tool
async def search_schedule(
  query: Annotated[str | None, "찾고자 하는 일정 키워드나 제목 (제목/설명 통합 검색)"] = None,
  start_at: Annotated[str | None, "조회 범위 시작 일시 (ISO 8601 형식)"] = None,
  end_at: Annotated[str | None, "조회 범위 종료 일시 (ISO 8601 형식)"] = None,
  max_results: Annotated[int, "최대 검색 결과 수"] = 10,
  *,
  config: RunnableConfig,
) -> list[GoogleCalendarEventModel] | str:
  """조건에 맞는 일정을 데이터베이스에서 검색하여 조회합니다. 적어도 하나의 조건(키워드 또는 기간)이 필요합니다."""
  configurable = config.get("configurable", {})
  user_id = configurable.get("user_id")
  calendar_id = configurable.get("calendar_id")
  schedule_service: ScheduleService | None = configurable.get("schedule_service")

  if not user_id or not schedule_service:
    return "오류: 사용자 정보 또는 일정 서비스 인스턴스를 찾을 수 없습니다."

  if not query and not start_at and not end_at:
    return "오류: 검색어 또는 조회 기간 중 적어도 하나는 제공되어야 합니다."

  try:
    # 1. 시간 파싱 및 타임존 설정
    dt_start = None
    dt_end = None
    minutes_offset = configurable.get("minutes_offset", 540)
    tz = timezone(timedelta(minutes=minutes_offset))

    if start_at:
      dt_start = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
      if dt_start.tzinfo is None:
        dt_start = dt_start.replace(tzinfo=tz)

    if end_at:
      dt_end = datetime.fromisoformat(end_at.replace("Z", "+00:00"))
      if dt_end.tzinfo is None:
        dt_end = dt_end.replace(tzinfo=tz)

    # 2. 검색 필터 및 임베딩 생성 (질의어가 있는 경우)
    query_vector = None
    if query and schedule_service._embedding_service:
      query_vector = await schedule_service._embedding_service.embedding(query)

    filters = ScheduleSearchFilter(
      start_at=dt_start,
      end_at=dt_end,
      keyword=query,
      query_vector=query_vector,
      google_calendar_id=calendar_id,
      limit=max_results,
    )

    # 3. 검색 수행
    results = schedule_service.read_schedules(owner_user_id=user_id, filters=filters)

    if not results:
      return []

    # 4. 결과 리턴 (LLM에 도메인 모델 인스턴스의 리스트로 반환)
    return list(results)

  except Exception as e:
    return json.dumps({"status": "error", "message": f"일정 검색 중 오류가 발생했습니다: {e!s}"}, ensure_ascii=False)
