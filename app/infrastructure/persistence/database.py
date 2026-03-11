import logging
from collections.abc import Generator

from sqlmodel import Session
from sqlmodel import create_engine

from app.core.config.environment import settings

logger = logging.getLogger(__name__)

# Supabase Postgresql URL을 SQLAlchemy 엔진용으로 생성합니다.
# Supabase 연결 URL이 보통 postgresql:// 로 시작하는데,
# 때에 따라 postgresql+psycopg2:// 등으로 변환할 필요가 있을 수 있으나
# 여기서는 기본적으로 sqlmodel에서 지원하는 postgresql:// 로 가정합니다.

# pool_pre_ping: DB 연결 끊김 방지
# psycopg (v3)를 사용하도록 드라이버를 명시합니다.
db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
  db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(
  db_url,
  echo=False,
  pool_pre_ping=True,
  pool_recycle=3600,
  connect_args={"options": f"-c search_path={settings.SUPABASE_SCHEMA}"},
)


def get_session() -> Generator[Session, None, None]:
  """FastAPI의 Depends에서 활용될 전역 데이터베이스 세션 제너레이터입니다."""
  with Session(engine) as session:
    yield session
