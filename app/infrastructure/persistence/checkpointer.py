import asyncio
import logging
from contextlib import AsyncExitStack

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from app.core.config.environment import settings

logger = logging.getLogger(__name__)


class Checkpointer:
  """LangGraph의 상태 영속화를 위한 PostgreSQL 체크포인터 관리 클래스입니다. (Infrastructure Layer)
  비동기 환경(FastAPI)을 위해 AsyncPostgresSaver를 사용합니다.
  """

  _instance = None
  _saver: AsyncPostgresSaver | None = None
  _exit_stack: AsyncExitStack | None = None

  def __new__(cls):
    if cls._instance is None:
      cls._instance = super().__new__(cls)
    return cls._instance

  async def get_checkpointer(self) -> AsyncPostgresSaver:
    """랑그래프 워크플로우에 주입할 AsyncPostgresSaver 인스턴스를 반환합니다."""
    if self._saver is None:
      conn_url = settings.DATABASE_URL
      try:
        self._exit_stack = AsyncExitStack()

        # AsyncConnectionPool을 생성하여 FastAPI의 동시성을 안전하게 처리합니다.
        pool_kwargs = {
          "autocommit": True,
          "prepare_threshold": 0,
        }
        pool = AsyncConnectionPool(
          conninfo=conn_url,
          max_size=20,
          kwargs=pool_kwargs,
        )
        await self._exit_stack.enter_async_context(pool)

        saver = AsyncPostgresSaver(pool)  # pyright: ignore[reportArgumentType]

        # 체크포인터 관련 테이블이 없으면 자동 생성합니다.
        await saver.setup()
        self._saver = saver
        logger.info("[Checkpointer] AsyncPostgresSaver (Connection Pool) 초기화 성공")
      except Exception as e:
        logger.error(f"[Checkpointer] AsyncPostgresSaver 초기화 실패: {e}")
        if self._exit_stack:
          await self._exit_stack.aclose()
        raise

    if self._saver is None:
      raise RuntimeError("AsyncPostgresSaver could not be initialized.")

    return self._saver

  async def delete_session(self, session_id: str) -> None:
    """특정 session_id에 해당하는 모든 체크포인트 데이터를 삭제합니다."""
    saver = await self.get_checkpointer()
    await saver.adelete_thread(session_id)
    logger.info(f"[Checkpointer] session '{session_id}' 데이터 삭제 완료")

  async def delete_sessions(self, session_ids: list[str]) -> None:
    """여러 session_id의 체크포인트 데이터를 병렬로 삭제합니다."""
    await asyncio.gather(*[self.delete_session(sid) for sid in session_ids])
    logger.info(f"[Checkpointer] {len(session_ids)}개 세션 삭제 완료")

  async def close(self):
    """애플리케이션 종료 시 DB 연결을 닫습니다."""
    if self._exit_stack:
      await self._exit_stack.aclose()
      self._saver = None
      self._exit_stack = None
      logger.info("[Checkpointer] AsyncPostgresSaver 연결이 닫혔습니다.")


# 전역 인스턴스 제공
checkpointer = Checkpointer()
