"""벡터 검색 인프라 제거 및 PGroonga 전문 검색 도입

Revision ID: a1b2c3d4e5f6
Revises: 21b5c34cb1bb
Create Date: 2026-03-24 16:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "21b5c34cb1bb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ==================================================================================================
# PGroonga 검색 도입
# --------------------------------------------------------------------------------------------------
# 기존 벡터 검색을 제거하고 PGroonga를 활용한 전문 검색 인프라 구축
# ==================================================================================================
def upgrade() -> None:
  # ── 1. FK 제약 조건 제거 ──
  op.drop_constraint(
    "google_calendar_events_embedding_id_fkey",
    "google_calendar_events",
    type_="foreignkey",
  )
  # memos, todos는 테이블 생성 시 이름 없이 FK가 걸렸으므로 명시적으로 찾아야 합니다.
  # Alembic 자동 생성 규칙: {table}_{column}_fkey
  op.execute("""
    ALTER TABLE public.memos
    DROP CONSTRAINT IF EXISTS memos_embedding_id_fkey;
  """)
  op.execute("""
    ALTER TABLE public.todos
    DROP CONSTRAINT IF EXISTS todos_embedding_id_fkey;
  """)

  # ── 2. embedding_id 컬럼 삭제 (3개 테이블) ──
  op.drop_column("google_calendar_events", "embedding_id")
  op.drop_column("memos", "embedding_id")
  op.drop_column("todos", "embedding_id")

  # ── 3. 임베딩 테이블 삭제 (자식 → 부모 순서로 DROP) ──
  op.drop_table("event_embeddings_1024")
  op.drop_table("event_embeddings_1536")
  op.drop_table("event_embeddings_768")
  op.drop_index(
    op.f("ix_event_embeddings_base_model_name"),
    table_name="event_embeddings_base",
  )
  op.drop_table("event_embeddings_base")

  # ── 4. 기존 tsvector GIN 인덱스 제거 (메모 검색용) ──
  op.execute("DROP INDEX IF EXISTS ix_memos_search;")

  # ── 5. pgroonga 확장 활성화 및 전문 검색 인덱스 생성 ──
  op.execute("CREATE EXTENSION IF NOT EXISTS pgroonga;")

  # summary 컬럼 타입을 Text로 변경 (pgroonga 인덱싱 크기 제한 회피)
  op.alter_column(
    "google_calendar_events",
    "summary",
    existing_type=sa.String(length=1024),
    type_=sa.Text(),
    existing_nullable=True,
  )

  op.execute("""
    CREATE INDEX IF NOT EXISTS ix_google_calendar_events_pgroonga
    ON public.google_calendar_events
    USING pgroonga (summary, description);
  """)

  op.execute("""
    CREATE INDEX IF NOT EXISTS ix_todos_pgroonga
    ON public.todos
    USING pgroonga (title, description);
  """)

  op.execute("""
    CREATE INDEX IF NOT EXISTS ix_memos_pgroonga
    ON public.memos
    USING pgroonga (title, content);
  """)


# ==================================================================================================
# 벡터 검색 복구
# --------------------------------------------------------------------------------------------------
# 도입된 PGroonga 인덱스를 삭제하고 이전 벡터 검색 환경 재구성
# ==================================================================================================
def downgrade() -> None:
  import pgvector.sqlalchemy

  # ── 1. pgroonga 인덱스 및 확장 제거 ──
  op.execute("DROP INDEX IF EXISTS ix_memos_pgroonga;")
  op.execute("DROP INDEX IF EXISTS ix_todos_pgroonga;")
  op.execute("DROP INDEX IF EXISTS ix_google_calendar_events_pgroonga;")
  op.execute("DROP EXTENSION IF EXISTS pgroonga;")

  op.alter_column(
    "google_calendar_events",
    "summary",
    existing_type=sa.Text(),
    type_=sa.String(length=1024),
    existing_nullable=True,
  )

  # ── 2. tsvector GIN 인덱스 복원 (메모 검색용) ──
  op.execute("""
    CREATE INDEX ix_memos_search ON public.memos
      USING GIN (to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(content, '')))
      WHERE deleted_at IS NULL;
  """)

  # ── 3. 임베딩 테이블 재생성 (부모 → 자식 순서) ──
  op.create_table(
    "event_embeddings_base",
    sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("model_name", sa.String(length=64), nullable=False),
    sa.Column("dimension", sa.Integer(), nullable=False),
    sa.Column(
      "created_at",
      sa.DateTime(timezone=True),
      server_default=sa.text("timezone('utc', now())"),
      nullable=False,
    ),
    sa.PrimaryKeyConstraint("id"),
  )
  op.create_index(
    op.f("ix_event_embeddings_base_model_name"),
    "event_embeddings_base",
    ["model_name"],
    unique=False,
  )
  op.create_table(
    "event_embeddings_1024",
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column(
      "embedding",
      pgvector.sqlalchemy.vector.VECTOR(dim=1024),
      nullable=False,
    ),
    sa.ForeignKeyConstraint(["id"], ["event_embeddings_base.id"], ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id"),
  )
  op.create_table(
    "event_embeddings_1536",
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column(
      "embedding",
      pgvector.sqlalchemy.vector.VECTOR(dim=1536),
      nullable=False,
    ),
    sa.ForeignKeyConstraint(["id"], ["event_embeddings_base.id"], ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id"),
  )
  op.create_table(
    "event_embeddings_768",
    sa.Column("id", sa.Integer(), nullable=False),
    sa.Column(
      "embedding",
      pgvector.sqlalchemy.vector.VECTOR(dim=768),
      nullable=False,
    ),
    sa.ForeignKeyConstraint(["id"], ["event_embeddings_base.id"], ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id"),
  )

  # ── 4. embedding_id 컬럼 및 FK 재생성 ──
  op.add_column(
    "google_calendar_events",
    sa.Column("embedding_id", sa.Integer(), nullable=True),
  )
  op.create_foreign_key(
    "google_calendar_events_embedding_id_fkey",
    "google_calendar_events",
    "event_embeddings_base",
    ["embedding_id"],
    ["id"],
    ondelete="SET NULL",
  )

  op.add_column(
    "memos",
    sa.Column("embedding_id", sa.Integer(), nullable=True),
  )
  op.create_foreign_key(
    "memos_embedding_id_fkey",
    "memos",
    "event_embeddings_base",
    ["embedding_id"],
    ["id"],
    ondelete="SET NULL",
  )

  op.add_column(
    "todos",
    sa.Column("embedding_id", sa.Integer(), nullable=True),
  )
  op.create_foreign_key(
    "todos_embedding_id_fkey",
    "todos",
    "event_embeddings_base",
    ["embedding_id"],
    ["id"],
    ondelete="SET NULL",
  )
