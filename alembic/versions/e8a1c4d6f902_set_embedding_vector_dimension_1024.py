"""google_calendar_events embedding 차원을 1024로 고정

Revision ID: e8a1c4d6f902
Revises: c12b9f8a7d3e
Create Date: 2026-02-13 22:05:00.000000

"""

from typing import Sequence
from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8a1c4d6f902"
down_revision: Union[str, Sequence[str], None] = "c12b9f8a7d3e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  """Upgrade schema."""
  # HNSW 인덱스 생성 전, embedding 컬럼을 고정 차원 vector(1024)로 변환합니다.
  op.execute(
    """
    ALTER TABLE public.google_calendar_events
    ALTER COLUMN embedding TYPE extensions.vector(1024)
    USING embedding::extensions.vector(1024);
    """
  )


def downgrade() -> None:
  """Downgrade schema."""
  op.execute(
    """
    ALTER TABLE public.google_calendar_events
    ALTER COLUMN embedding TYPE extensions.vector
    USING embedding::extensions.vector;
    """
  )
