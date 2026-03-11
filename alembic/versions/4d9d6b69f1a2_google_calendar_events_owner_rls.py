"""google_calendar_events 소유자 컬럼 및 RLS 정책 추가

Revision ID: 4d9d6b69f1a2
Revises: b8e6622c4a0c
Create Date: 2026-02-13 20:45:00.000000

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "4d9d6b69f1a2"
down_revision: Union[str, Sequence[str], None] = "b8e6622c4a0c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  """Upgrade schema."""
  # 소유자(Auth UUID) 컬럼을 추가하고 auth.users(id)와 FK를 연결합니다.
  op.add_column(
    "google_calendar_events",
    sa.Column("owner_user_id", postgresql.UUID(as_uuid=False), nullable=True),
  )
  op.create_index(
    op.f("ix_google_calendar_events_owner_user_id"),
    "google_calendar_events",
    ["owner_user_id"],
    unique=False,
  )
  op.create_foreign_key(
    "fk_google_calendar_events_owner_user_id_auth_users",
    "google_calendar_events",
    "users",
    ["owner_user_id"],
    ["id"],
    source_schema="public",
    referent_schema="auth",
    ondelete="CASCADE",
  )

  # Data API 최소 권한 원칙을 위해 권한 상태를 명시적으로 고정합니다.
  # (역연산 시 b8e6622c4a0c의 ALL 권한 상태로 정확히 복원하기 위함)
  op.execute("REVOKE ALL ON TABLE public.google_calendar_events FROM anon;")
  op.execute("REVOKE ALL ON SEQUENCE public.google_calendar_events_id_seq FROM anon;")

  # authenticated 역할에는 정책으로 제어할 DML 권한만 부여합니다.
  op.execute("REVOKE ALL ON TABLE public.google_calendar_events FROM authenticated;")
  op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.google_calendar_events TO authenticated;")
  op.execute("REVOKE ALL ON SEQUENCE public.google_calendar_events_id_seq FROM authenticated;")
  op.execute("GRANT USAGE, SELECT ON SEQUENCE public.google_calendar_events_id_seq TO authenticated;")

  # service_role도 상태를 명시해 migration의 입력 상태 의존성을 제거합니다.
  op.execute("REVOKE ALL ON TABLE public.google_calendar_events FROM service_role;")
  op.execute("GRANT ALL ON TABLE public.google_calendar_events TO service_role;")
  op.execute("REVOKE ALL ON SEQUENCE public.google_calendar_events_id_seq FROM service_role;")
  op.execute("GRANT ALL ON SEQUENCE public.google_calendar_events_id_seq TO service_role;")

  # owner_user_id = auth.uid() 인 행만 접근하도록 RLS를 활성화합니다.
  op.execute("ALTER TABLE public.google_calendar_events ENABLE ROW LEVEL SECURITY;")

  op.execute(
    """
    CREATE POLICY google_calendar_events_select_own
    ON public.google_calendar_events
    FOR SELECT
    TO authenticated
    USING (owner_user_id = (select auth.uid()));
    """
  )
  op.execute(
    """
    CREATE POLICY google_calendar_events_insert_own
    ON public.google_calendar_events
    FOR INSERT
    TO authenticated
    WITH CHECK (owner_user_id = (select auth.uid()));
    """
  )
  op.execute(
    """
    CREATE POLICY google_calendar_events_update_own
    ON public.google_calendar_events
    FOR UPDATE
    TO authenticated
    USING (owner_user_id = (select auth.uid()))
    WITH CHECK (owner_user_id = (select auth.uid()));
    """
  )
  op.execute(
    """
    CREATE POLICY google_calendar_events_delete_own
    ON public.google_calendar_events
    FOR DELETE
    TO authenticated
    USING (owner_user_id = (select auth.uid()));
    """
  )


def downgrade() -> None:
  """Downgrade schema."""
  op.execute("DROP POLICY IF EXISTS google_calendar_events_delete_own ON public.google_calendar_events;")
  op.execute("DROP POLICY IF EXISTS google_calendar_events_update_own ON public.google_calendar_events;")
  op.execute("DROP POLICY IF EXISTS google_calendar_events_insert_own ON public.google_calendar_events;")
  op.execute("DROP POLICY IF EXISTS google_calendar_events_select_own ON public.google_calendar_events;")
  op.execute("ALTER TABLE public.google_calendar_events DISABLE ROW LEVEL SECURITY;")

  # 초기 상태와 동일하게 anon/authenticated/service_role 전체 권한으로 복원합니다.
  op.execute("GRANT ALL ON TABLE public.google_calendar_events TO anon;")
  op.execute("GRANT ALL ON TABLE public.google_calendar_events TO authenticated;")
  op.execute("GRANT ALL ON TABLE public.google_calendar_events TO service_role;")
  op.execute("GRANT ALL ON SEQUENCE public.google_calendar_events_id_seq TO anon;")
  op.execute("GRANT ALL ON SEQUENCE public.google_calendar_events_id_seq TO authenticated;")
  op.execute("GRANT ALL ON SEQUENCE public.google_calendar_events_id_seq TO service_role;")

  op.drop_constraint(
    "fk_google_calendar_events_owner_user_id_auth_users",
    "google_calendar_events",
    schema="public",
    type_="foreignkey",
  )
  op.drop_index(op.f("ix_google_calendar_events_owner_user_id"), table_name="google_calendar_events")
  op.drop_column("google_calendar_events", "owner_user_id")
