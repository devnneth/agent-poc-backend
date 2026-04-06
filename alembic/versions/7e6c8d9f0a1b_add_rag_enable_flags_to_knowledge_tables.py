"""Add rag enable flags to knowledge tables

Revision ID: 7e6c8d9f0a1b
Revises: 5a9e5d1b7c3f
Create Date: 2026-04-05 15:10:00.000000

"""

from typing import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7e6c8d9f0a1b"
down_revision: Union[str, Sequence[str], None] = "5a9e5d1b7c3f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  """Upgrade schema."""
  op.add_column(
    "knowledges",
    sa.Column(
      "is_rag_enabled",
      sa.Boolean(),
      nullable=False,
      server_default=sa.text("true"),
    ),
  )
  op.add_column(
    "knowledge_sources",
    sa.Column(
      "is_rag_enabled",
      sa.Boolean(),
      nullable=False,
      server_default=sa.text("true"),
    ),
  )


def downgrade() -> None:
  """Downgrade schema."""
  op.drop_column("knowledge_sources", "is_rag_enabled")
  op.drop_column("knowledges", "is_rag_enabled")
