"""Remove redundant status column from knowledge sources

Revision ID: 9f3c7b1a2d4e
Revises: 6c4c4f9a2b1e
Create Date: 2026-03-27 11:20:00.000000

"""

from typing import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "9f3c7b1a2d4e"
down_revision: Union[str, Sequence[str], None] = "6c4c4f9a2b1e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


entitystatus = postgresql.ENUM(
  "PENDING",
  "PROCESSING",
  "COMPLETED",
  "FAILED",
  "DELETING",
  "DELETED",
  name="entitystatus",
)


# ==================================================================================================
# 상태 필드 제거
# --------------------------------------------------------------------------------------------------
# Knowledge 소스 테이블에서 불필요해진 상태값 컬럼 삭제
# ==================================================================================================
def upgrade() -> None:
  op.drop_column("knowledge_sources", "status")
  entitystatus.drop(op.get_bind(), checkfirst=True)


# ==================================================================================================
# 상태 필드 복구
# --------------------------------------------------------------------------------------------------
# 삭제되었던 Knowledge 소스 상태값 컬럼 다시 추가
# ==================================================================================================
def downgrade() -> None:
  entitystatus.create(op.get_bind(), checkfirst=True)
  op.add_column(
    "knowledge_sources",
    sa.Column(
      "status",
      entitystatus,
      nullable=False,
      server_default=sa.text("'PENDING'"),
    ),
  )
  op.execute("""
    UPDATE knowledge_sources
    SET status = CASE
      WHEN deleted_at IS NOT NULL THEN 'DELETED'::entitystatus
      ELSE 'PENDING'::entitystatus
    END
  """)
  op.alter_column("knowledge_sources", "status", server_default=None)
