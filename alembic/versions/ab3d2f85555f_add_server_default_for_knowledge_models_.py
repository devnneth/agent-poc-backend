"""Add server_default for knowledge models id

Revision ID: ab3d2f85555f
Revises: f6282e63e5db
Create Date: 2026-03-25 16:27:09.257864

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ab3d2f85555f"
down_revision: Union[str, Sequence[str], None] = "f6282e63e5db"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ==================================================================================================
# 서버 기본값 설정
# --------------------------------------------------------------------------------------------------
# Knowledge 모델 필드에 데이터베이스 차원의 기본값 제약 추가
# ==================================================================================================
def upgrade() -> None:
  # knowledge 테이블들에 대해 id 컬럼의 DEFAULT 값을 uuid_generate_v4()로 설정합니다.
  op.execute("ALTER TABLE knowledges ALTER COLUMN id SET DEFAULT uuid_generate_v4()")
  op.execute("ALTER TABLE knowledge_sources ALTER COLUMN id SET DEFAULT uuid_generate_v4()")
  op.execute("ALTER TABLE knowledge_chunks ALTER COLUMN id SET DEFAULT uuid_generate_v4()")


# ==================================================================================================
# 서버 기본값 제거
# --------------------------------------------------------------------------------------------------
# Knowledge 모델 필드에 적용된 DB 기본값 제약 해제
# ==================================================================================================
def downgrade() -> None:
  # DEFAULT 값을 제거합니다.
  op.execute("ALTER TABLE knowledges ALTER COLUMN id DROP DEFAULT")
  op.execute("ALTER TABLE knowledge_sources ALTER COLUMN id DROP DEFAULT")
  op.execute("ALTER TABLE knowledge_chunks ALTER COLUMN id DROP DEFAULT")
