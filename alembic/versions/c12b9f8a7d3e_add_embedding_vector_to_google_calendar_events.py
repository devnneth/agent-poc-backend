"""google_calendar_events 임베딩 vector 컬럼 추가

Revision ID: c12b9f8a7d3e
Revises: 4d9d6b69f1a2
Create Date: 2026-02-13 21:20:00.000000

"""

from typing import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "c12b9f8a7d3e"
down_revision: Union[str, Sequence[str], None] = "4d9d6b69f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  """Upgrade schema."""
  # pgvector 확장이 비활성화된 환경에서도 마이그레이션이 실패하지 않도록 선행 보장합니다.
  op.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;")

  # 임베딩 생성 시점이 비동기일 수 있으므로 nullable 컬럼으로 먼저 추가합니다.
  op.add_column(
    "google_calendar_events",
    sa.Column("embedding", Vector(), nullable=True),
  )


def downgrade() -> None:
  """Downgrade schema."""
  op.drop_column("google_calendar_events", "embedding")
