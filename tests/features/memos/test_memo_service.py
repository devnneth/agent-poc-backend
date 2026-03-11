from unittest.mock import MagicMock

import pytest

from app.features.memos.memo_db_service import MemoDBService
from app.features.memos.memo_dto import MemoCreate
from app.features.memos.memo_dto import MemoUpdate
from app.features.memos.memo_service import MemoService


@pytest.mark.asyncio
async def test_create_memo_without_embedding_service_skips_embedding():
  """임베딩 비활성화 시 임베딩 없이 메모 생성이 가능해야 합니다."""
  db_service = MagicMock(spec=MemoDBService)
  service = MemoService(db_service=db_service, embedding_service=None)
  payload = MemoCreate(title="회의 메모")

  await service.create_memo(owner_user_id="user-123", payload=payload)

  db_service.create_memo.assert_called_once_with(
    owner_user_id="user-123",
    payload=payload,
    model_name=None,
    embedding=None,
  )


@pytest.mark.asyncio
async def test_update_memo_without_embedding_service_skips_embedding():
  """임베딩 비활성화 시 임베딩 없이 메모 수정이 가능해야 합니다."""
  db_service = MagicMock(spec=MemoDBService)
  db_model = MagicMock()
  db_service.get_memo.return_value = db_model
  service = MemoService(db_service=db_service, embedding_service=None)
  payload = MemoUpdate(title="수정된 메모")

  await service.update_memo(owner_user_id="user-123", db_id=1, payload=payload)

  db_service.update_memo.assert_called_once_with(
    db_model,
    payload,
    model_name=None,
    updated_embedding=None,
  )
