"""google_calendar_events datetime 컬럼 전환 및 검색 인덱스 추가

Revision ID: f2a4d3c1b8e9
Revises: d7f3a1b9c2e4
Create Date: 2026-02-13 23:20:00.000000

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2a4d3c1b8e9"
down_revision: Union[str, Sequence[str], None] = "d7f3a1b9c2e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  """Upgrade schema."""
  # 부분 문자열 검색 최적화를 위해 pg_trgm 확장을 준비합니다.
  op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA extensions;")

  # payload(JSON) 기반 시간 정보를 정규화 datetime 컬럼으로 이전합니다.
  op.add_column(
    "google_calendar_events",
    sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
  )
  op.add_column(
    "google_calendar_events",
    sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
  )
  op.add_column(
    "google_calendar_events",
    sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
  )
  op.add_column(
    "google_calendar_events",
    sa.Column(
      "created_at",
      sa.DateTime(timezone=True),
      nullable=True,
      server_default=sa.text("timezone('utc', now())"),
    ),
  )
  op.add_column(
    "google_calendar_events",
    sa.Column(
      "updated_at",
      sa.DateTime(timezone=True),
      nullable=True,
      server_default=sa.text("timezone('utc', now())"),
    ),
  )

  op.execute(
    """
    UPDATE public.google_calendar_events
    SET
      start_at = COALESCE(
        NULLIF(start_payload ->> 'dateTime', '')::timestamptz,
        (NULLIF(start_payload ->> 'date', '')::date::timestamp AT TIME ZONE 'UTC')
      ),
      end_at = COALESCE(
        NULLIF(end_payload ->> 'dateTime', '')::timestamptz,
        (NULLIF(end_payload ->> 'date', '')::date::timestamp AT TIME ZONE 'UTC')
      ),
      created_at = COALESCE(created_at, timezone('utc', now())),
      updated_at = COALESCE(updated_at, timezone('utc', now()));
    """
  )

  op.alter_column("google_calendar_events", "start_at", nullable=False)
  op.alter_column("google_calendar_events", "end_at", nullable=False)
  op.alter_column("google_calendar_events", "created_at", nullable=False)
  op.alter_column("google_calendar_events", "updated_at", nullable=False)

  # Google API 실패 생성 케이스를 허용하기 위해 google_event_id를 nullable로 전환합니다.
  op.alter_column(
    "google_calendar_events",
    "google_event_id",
    existing_type=sa.String(length=255),
    nullable=True,
  )

  # 기존 유니크 제약은 제거하고, google_event_id가 있을 때만 유니크를 보장합니다.
  op.execute(
    """
    ALTER TABLE public.google_calendar_events
    DROP CONSTRAINT IF EXISTS uq_google_calendar_events_calendar_event;
    """
  )
  op.create_index(
    "uq_google_calendar_events_calendar_event_not_null",
    "google_calendar_events",
    ["google_calendar_id", "google_event_id"],
    unique=True,
    postgresql_where=sa.text("google_event_id IS NOT NULL"),
  )

  # 기간/삭제 조건 조회를 위한 복합 인덱스를 추가합니다.
  op.create_index(
    "ix_google_calendar_events_owner_user_start_at",
    "google_calendar_events",
    ["owner_user_id", "start_at"],
    unique=False,
  )
  op.create_index(
    "ix_google_calendar_events_owner_user_end_at",
    "google_calendar_events",
    ["owner_user_id", "end_at"],
    unique=False,
  )
  op.create_index(
    "ix_google_calendar_events_owner_user_deleted_at",
    "google_calendar_events",
    ["owner_user_id", "deleted_at"],
    unique=False,
  )

  # 제목/본문 LIKE 검색 최적화를 위한 trigram GIN 인덱스입니다.
  op.execute(
    """
    CREATE INDEX IF NOT EXISTS ix_google_calendar_events_summary_trgm
    ON public.google_calendar_events
    USING gin (summary extensions.gin_trgm_ops)
    WHERE summary IS NOT NULL;
    """
  )
  op.execute(
    """
    CREATE INDEX IF NOT EXISTS ix_google_calendar_events_description_trgm
    ON public.google_calendar_events
    USING gin (description extensions.gin_trgm_ops)
    WHERE description IS NOT NULL;
    """
  )

  # datetime 컬럼 전환 완료 후 payload 계열 컬럼을 정리합니다.
  op.drop_column("google_calendar_events", "start_payload")
  op.drop_column("google_calendar_events", "end_payload")
  op.drop_column("google_calendar_events", "reminders_payload")


def downgrade() -> None:
  """Downgrade schema."""
  # 기존 구조 복원을 위해 payload 컬럼을 다시 추가합니다.
  op.add_column(
    "google_calendar_events",
    sa.Column("start_payload", sa.JSON(), nullable=True),
  )
  op.add_column(
    "google_calendar_events",
    sa.Column("end_payload", sa.JSON(), nullable=True),
  )
  op.add_column(
    "google_calendar_events",
    sa.Column("reminders_payload", sa.JSON(), nullable=True),
  )

  op.execute(
    """
    UPDATE public.google_calendar_events
    SET
      start_payload = json_build_object(
        'dateTime',
        to_char(start_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
      )::json,
      end_payload = json_build_object(
        'dateTime',
        to_char(end_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
      )::json
    WHERE start_payload IS NULL OR end_payload IS NULL;
    """
  )
  op.alter_column("google_calendar_events", "start_payload", nullable=False)
  op.alter_column("google_calendar_events", "end_payload", nullable=False)

  op.execute("DROP INDEX IF EXISTS public.ix_google_calendar_events_summary_trgm;")
  op.execute("DROP INDEX IF EXISTS public.ix_google_calendar_events_description_trgm;")

  op.drop_index("ix_google_calendar_events_owner_user_deleted_at", table_name="google_calendar_events")
  op.drop_index("ix_google_calendar_events_owner_user_end_at", table_name="google_calendar_events")
  op.drop_index("ix_google_calendar_events_owner_user_start_at", table_name="google_calendar_events")

  op.drop_index("uq_google_calendar_events_calendar_event_not_null", table_name="google_calendar_events")

  # downgrade 시 null google_event_id를 정규화해 기존 not-null 제약을 만족시킵니다.
  op.execute(
    """
    UPDATE public.google_calendar_events
    SET google_event_id = '__missing__' || id::text
    WHERE google_event_id IS NULL;
    """
  )

  op.alter_column(
    "google_calendar_events",
    "google_event_id",
    existing_type=sa.String(length=255),
    nullable=False,
  )
  op.create_unique_constraint(
    "uq_google_calendar_events_calendar_event",
    "google_calendar_events",
    ["google_calendar_id", "google_event_id"],
  )

  op.drop_column("google_calendar_events", "updated_at")
  op.drop_column("google_calendar_events", "created_at")
  op.drop_column("google_calendar_events", "deleted_at")
  op.drop_column("google_calendar_events", "end_at")
  op.drop_column("google_calendar_events", "start_at")
