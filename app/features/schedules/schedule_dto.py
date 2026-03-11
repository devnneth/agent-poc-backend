from datetime import UTC
from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from app.infrastructure.models.google_calendar_event_model import GoogleCalendarEventModel


class ScheduleCreate(BaseModel):
  """일정 생성용 DTO입니다."""

  google_calendar_id: str | None = Field(default=None, description="대상 캘린더 ID")
  summary: str | None = Field(default=None, description="일정 제목")
  description: str | None = Field(default=None, description="일정 상세 내용")
  start_at: datetime = Field(description="일정 시작 시간")
  end_at: datetime = Field(description="일정 종료 시간")
  color_id: str | None = Field(default=None, description="구글 캘린더 색상 ID")
  icon: str | None = Field(default=None, description="프론트엔드 아이콘")

  def to_model(self, owner_user_id: str, google_event_id: str | None = None) -> GoogleCalendarEventModel:
    now = datetime.now(UTC)
    return GoogleCalendarEventModel(
      owner_user_id=owner_user_id,
      google_calendar_id=self.google_calendar_id,
      google_event_id=google_event_id,
      summary=self.summary,
      description=self.description,
      start_at=self.start_at,
      end_at=self.end_at,
      color_id=self.color_id,
      icon=self.icon,
      created_at=now,
      updated_at=now,
    )


class ScheduleUpdate(BaseModel):
  """일정 수정용 옵셔널 DTO입니다."""

  summary: str | None = None
  description: str | None = None
  start_at: datetime | None = None
  end_at: datetime | None = None
  color_id: str | None = None
  icon: str | None = None


class ScheduleSearchFilter(BaseModel):
  """하이브리드 조회를 위한 필터 DTO입니다."""

  start_at: datetime | None = Field(default=None, description="조회 시작 기간 (이 시점 이후의 일정 검색)")
  end_at: datetime | None = Field(default=None, description="조회 종료 기간 (이 시점 이전의 일정 검색)")
  keyword: str | None = Field(default=None, description="검색할 키워드 (Hybrid 검색용)")
  query_vector: list[float] | None = Field(default=None, description="키워드의 임베딩 벡터 (Hybrid 검색용)")
  google_calendar_id: str | None = Field(default=None, description="특정 캘린더 지정을 원할 경우 사용")
  limit: int | None = Field(default=None, description="최대 검색 결과 수")
