"""knowledge 테이블 RLS 정책 추가

Revision ID: 5a9e5d1b7c3f
Revises: 9f3c7b1a2d4e
Create Date: 2026-04-04 21:05:00.000000

"""

from typing import Sequence
from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5a9e5d1b7c3f"
down_revision: Union[str, Sequence[str], None] = "9f3c7b1a2d4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


KNOWLEDGE_TABLES: tuple[str, ...] = (
  "knowledges",
  "knowledge_sources",
  "knowledge_chunks",
)


# ==================================================================================================
# 지식 테이블 RLS 정책 추가
# --------------------------------------------------------------------------------------------------
# Knowledge 관련 테이블에 사용자별 데이터 접근 제어를 위한 RLS 적용
# ==================================================================================================
def upgrade() -> None:
  for table_name in KNOWLEDGE_TABLES:
    # Supabase Data API는 테이블 권한과 RLS 정책이 모두 있어야 정상 동작합니다.
    op.execute(f"REVOKE ALL ON TABLE public.{table_name} FROM anon;")

    op.execute(f"REVOKE ALL ON TABLE public.{table_name} FROM authenticated;")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.{table_name} TO authenticated;")

    op.execute(f"REVOKE ALL ON TABLE public.{table_name} FROM service_role;")
    op.execute(f"GRANT ALL ON TABLE public.{table_name} TO service_role;")

    op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY;")

    op.execute(
      f"""
      CREATE POLICY {table_name}_select_own ON public.{table_name}
        FOR SELECT TO authenticated
        USING (user_id = (select auth.uid()));
      """
    )
    op.execute(
      f"""
      CREATE POLICY {table_name}_insert_own ON public.{table_name}
        FOR INSERT TO authenticated
        WITH CHECK (user_id = (select auth.uid()));
      """
    )
    op.execute(
      f"""
      CREATE POLICY {table_name}_update_own ON public.{table_name}
        FOR UPDATE TO authenticated
        USING (user_id = (select auth.uid()))
        WITH CHECK (user_id = (select auth.uid()));
      """
    )
    op.execute(
      f"""
      CREATE POLICY {table_name}_delete_own ON public.{table_name}
        FOR DELETE TO authenticated
        USING (user_id = (select auth.uid()));
      """
    )


# ==================================================================================================
# 지식 테이블 RLS 정책 제거
# --------------------------------------------------------------------------------------------------
# Knowledge 관련 테이블에 설정된 RLS 정책 및 권한 변경 사항 복구
# ==================================================================================================
def downgrade() -> None:
  for table_name in reversed(KNOWLEDGE_TABLES):
    op.execute(f"DROP POLICY IF EXISTS {table_name}_delete_own ON public.{table_name};")
    op.execute(f"DROP POLICY IF EXISTS {table_name}_update_own ON public.{table_name};")
    op.execute(f"DROP POLICY IF EXISTS {table_name}_insert_own ON public.{table_name};")
    op.execute(f"DROP POLICY IF EXISTS {table_name}_select_own ON public.{table_name};")
    op.execute(f"ALTER TABLE public.{table_name} DISABLE ROW LEVEL SECURITY;")

    # 기존 migration과 동일하게 기본 전체 권한 상태로 되돌립니다.
    op.execute(f"GRANT ALL ON TABLE public.{table_name} TO anon;")
    op.execute(f"GRANT ALL ON TABLE public.{table_name} TO authenticated;")
    op.execute(f"GRANT ALL ON TABLE public.{table_name} TO service_role;")
