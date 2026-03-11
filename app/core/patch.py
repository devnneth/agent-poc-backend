import asyncio
import sys
import warnings


def apply_patches():
  """애플리케이션 실행 전 필요한 전역 패치 및 설정을 적용합니다."""

  # 1. Pydantic 2.x serialization 경고 억제
  # LangChain/Langfuse 사용 시 발생하는 'parsed' 필드 타입 불일치 경고를 무시합니다.
  warnings.filterwarnings(
    "ignore",
    message=".*Pydantic serializer warnings.*",
    category=UserWarning,
    module="pydantic.main",
  )

  # 2. Windows에서 PostgreSQL 드라이버(psycopg v3) 비동기 모드 사용 시 ProactorEventLoop 충돌을 방지하기 위한 설정
  if sys.platform == "win32":
    if not isinstance(asyncio.get_event_loop_policy(), asyncio.WindowsSelectorEventLoopPolicy):
      asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
