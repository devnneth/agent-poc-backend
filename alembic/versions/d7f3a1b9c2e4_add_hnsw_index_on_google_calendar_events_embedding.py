"""google_calendar_events embedding HNSW 인덱스 추가

Revision ID: d7f3a1b9c2e4
Revises: e8a1c4d6f902
Create Date: 2026-02-13 21:45:00.000000

"""

from typing import Sequence
from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7f3a1b9c2e4"
down_revision: Union[str, Sequence[str], None] = "e8a1c4d6f902"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  """Upgrade schema."""
  # 코사인 거리 기반 ANN 검색 성능 향상을 위해 HNSW 인덱스를 추가합니다.
  # NULL 임베딩은 검색 대상이 아니므로 부분 인덱스로 크기를 줄입니다.
  op.execute(
    """
    CREATE INDEX IF NOT EXISTS ix_google_calendar_events_embedding_hnsw
    ON public.google_calendar_events
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64)
    WHERE embedding IS NOT NULL;
    """
  )


def downgrade() -> None:
  """Downgrade schema."""
  op.execute("DROP INDEX IF EXISTS public.ix_google_calendar_events_embedding_hnsw;")
