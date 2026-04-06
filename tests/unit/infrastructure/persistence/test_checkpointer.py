from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest

from app.infrastructure.persistence.checkpointer import Checkpointer


# ==================================================================================================
# Prepared Statement 비활성화 검증
# --------------------------------------------------------------------------------------------------
# Supabase 커넥션 풀 충돌 방지 설정이 적용되는지 확인합니다
# ==================================================================================================
@pytest.mark.asyncio
async def test_get_checkpointer_disables_prepared_statements():
  checkpointer = Checkpointer()
  checkpointer._saver = None
  checkpointer._exit_stack = None

  mock_pool = AsyncMock()
  mock_saver = AsyncMock()
  mock_exit_stack = AsyncMock()
  mock_exit_stack.enter_async_context = AsyncMock(return_value=mock_pool)

  with (
    patch("app.infrastructure.persistence.checkpointer.AsyncExitStack", return_value=mock_exit_stack),
    patch(
      "app.infrastructure.persistence.checkpointer.AsyncConnectionPool",
      return_value=mock_pool,
    ) as mock_pool_cls,
    patch(
      "app.infrastructure.persistence.checkpointer.AsyncPostgresSaver",
      return_value=mock_saver,
    ),
  ):
    saver = await checkpointer.get_checkpointer()

  assert saver is mock_saver
  mock_pool_cls.assert_called_once()
  assert mock_pool_cls.call_args.kwargs["kwargs"]["prepare_threshold"] is None
  mock_saver.setup.assert_awaited_once()


# ==================================================================================================
# 세션 순차 삭제 검증
# --------------------------------------------------------------------------------------------------
# 충돌 방지를 위해 세션 삭제가 순차적으로 실행되는지 확인합니다
# ==================================================================================================
@pytest.mark.asyncio
async def test_delete_sessions_runs_sequentially():
  checkpointer = Checkpointer()
  session_ids = ["session-1", "session-2", "session-3"]
  deleted_ids: list[str] = []

  # ------------------------------------------------------------------------------------------------
  # 삭제 기록
  # ------------------------------------------------------------------------------------------------
  async def record_delete(session_id: str) -> None:
    deleted_ids.append(session_id)

  with patch.object(checkpointer, "delete_session", new=AsyncMock(side_effect=record_delete)) as mock_delete:
    await checkpointer.delete_sessions(session_ids)

  assert deleted_ids == session_ids
  assert mock_delete.await_count == len(session_ids)
