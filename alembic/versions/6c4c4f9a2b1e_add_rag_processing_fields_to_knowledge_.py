"""Add rag processing fields to knowledge sources

Revision ID: 6c4c4f9a2b1e
Revises: f6282e63e5db
Create Date: 2026-03-25 20:10:00.000000

"""

from typing import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "6c4c4f9a2b1e"
down_revision: Union[str, Sequence[str], None] = "ab3d2f85555f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


processingstatus = postgresql.ENUM("PENDING", "ING", "DONE", "ERROR", name="processingstatus")


# ==================================================================================================
# RAG 처리 필드 추가
# --------------------------------------------------------------------------------------------------
# 지식 소스 관리를 위해 RAG 처리 상태 및 정보 필드 확장
# ==================================================================================================
def upgrade() -> None:
  processingstatus.create(op.get_bind(), checkfirst=True)
  op.add_column(
    "knowledge_sources",
    sa.Column(
      "processing_status",
      processingstatus,
      nullable=False,
      server_default=sa.text("'PENDING'"),
    ),
  )
  op.add_column("knowledge_sources", sa.Column("processing_error_message", sa.Text(), nullable=True))
  op.add_column("knowledge_sources", sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True))
  op.add_column("knowledge_sources", sa.Column("processing_completed_at", sa.DateTime(timezone=True), nullable=True))
  op.add_column(
    "knowledge_sources",
    sa.Column("source_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
  )


# ==================================================================================================
# RAG 처리 필드 삭제
# --------------------------------------------------------------------------------------------------
# 지식 소스 테이블에서 확장된 RAG 처리 관련 필드 제거
# ==================================================================================================
def downgrade() -> None:
  op.drop_column("knowledge_sources", "source_metadata")
  op.drop_column("knowledge_sources", "processing_completed_at")
  op.drop_column("knowledge_sources", "processing_started_at")
  op.drop_column("knowledge_sources", "processing_error_message")
  op.drop_column("knowledge_sources", "processing_status")
  processingstatus.drop(op.get_bind(), checkfirst=True)
