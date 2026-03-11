from unittest.mock import MagicMock

import pytest

from app.features.todos.todo_db_service import TodoDBService
from app.features.todos.todo_dto import TodoCreate
from app.features.todos.todo_dto import TodoUpdate
from app.features.todos.todo_service import TodoService


@pytest.mark.asyncio
async def test_create_todo_without_embedding_service_skips_embedding():
  """임베딩 비활성화 시 임베딩 없이 할일 생성이 가능해야 합니다."""
  db_service = MagicMock(spec=TodoDBService)
  service = TodoService(db_service=db_service, embedding_service=None)
  payload = TodoCreate(title="운동")

  await service.create_todo(owner_user_id="user-123", payload=payload)

  db_service.create_todo.assert_called_once_with(
    owner_user_id="user-123",
    payload=payload,
    model_name=None,
    embedding=None,
  )


@pytest.mark.asyncio
async def test_update_todo_without_embedding_service_skips_embedding():
  """임베딩 비활성화 시 임베딩 없이 할일 수정이 가능해야 합니다."""
  db_service = MagicMock(spec=TodoDBService)
  db_model = MagicMock()
  db_service.get_todo.return_value = db_model
  service = TodoService(db_service=db_service, embedding_service=None)
  payload = TodoUpdate(title="변경된 할일")

  await service.update_todo(owner_user_id="user-123", db_id=1, payload=payload)

  db_service.update_todo.assert_called_once_with(
    db_model,
    payload,
    model_name=None,
    updated_embedding=None,
  )
