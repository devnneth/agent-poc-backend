from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field
from sqlmodel import SQLModel

from app.infrastructure.models.auth_user_model import AuthUserModel  # noqa: F401


class GoogleCalendarEventModel(SQLModel, table=True):
  """Google Calendar 이벤트 동기화에 필요한 최소 필드 모델."""

  __tablename__: str = "google_calendar_events"  # pyright: ignore[reportAssignmentType, reportIncompatibleVariableOverride]

  __table_args__ = (
    # google_event_id가 있는 경우에만 유니크를 보장합니다.
    Index(
      "uq_google_calendar_events_calendar_event_not_null",
      "google_calendar_id",
      "google_event_id",
      unique=True,
      postgresql_where=text("google_event_id IS NOT NULL"),
    ),
    # 사용자별 기간 검색 성능을 위한 복합 인덱스입니다.
    Index("ix_google_calendar_events_owner_user_start_at", "owner_user_id", "start_at"),
    Index("ix_google_calendar_events_owner_user_end_at", "owner_user_id", "end_at"),
    Index("ix_google_calendar_events_owner_user_deleted_at", "owner_user_id", "deleted_at"),
  )

  id: int | None = Field(
    default=None,
    sa_column=Column(Integer, primary_key=True, autoincrement=True),
  )
  google_calendar_id: str | None = Field(
    sa_column=Column(String(320), nullable=False, index=True),
    description="Events API 경로의 calendarId 값",
  )
  google_event_id: str | None = Field(
    default=None,
    sa_column=Column(String(255), nullable=True, index=True),
    description="Google Events 리소스 id 값",
  )

  owner_user_id: str | None = Field(
    default=None,
    sa_column=Column(
      UUID(as_uuid=False),
      ForeignKey("auth.users.id", ondelete="CASCADE"),
      nullable=True,
      index=True,
    ),
    description="소유자 Supabase Auth UUID(auth.users.id)",
  )

  summary: str | None = Field(default=None, sa_column=Column(String(1024), nullable=True))
  description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
  color_id: str | None = Field(default=None, sa_column=Column(String(32), nullable=True))
  icon: str | None = Field(
    default=None,
    sa_column=Column(String(128), nullable=True),
    description="프론트 선택 아이콘(Lucide 아이콘명)",
  )

  # 검색 조건 단순화를 위해 시작/종료 시각을 datetime 컬럼으로 관리합니다.
  start_at: datetime = Field(
    sa_column=Column(DateTime(timezone=True), nullable=False),
  )
  end_at: datetime = Field(
    sa_column=Column(DateTime(timezone=True), nullable=False),
  )

  deleted_at: datetime | None = Field(
    default=None,
    sa_column=Column(DateTime(timezone=True), nullable=True),
  )
  created_at: datetime = Field(
    sa_column=Column(
      DateTime(timezone=True),
      nullable=False,
      server_default=text("timezone('utc', now())"),
    ),
  )
  updated_at: datetime = Field(
    sa_column=Column(
      DateTime(timezone=True),
      nullable=False,
      server_default=text("timezone('utc', now())"),
    ),
  )

  # 벡터 검색용 임베딩 참조 컬럼입니다.
  embedding_id: int | None = Field(
    default=None,
    sa_column=Column(
      Integer,
      ForeignKey("event_embeddings_base.id", ondelete="SET NULL"),
      nullable=True,
    ),
    description="이벤트 임베딩 베이스 테이블 참조 ID",
  )
