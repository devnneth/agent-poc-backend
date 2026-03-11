from datetime import UTC
from datetime import datetime
from datetime import timedelta
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import PropertyMock

import pytest

from app.features.llm.embedding_service import EmbeddingService
from app.features.schedules.schedule_db_service import ScheduleDBService
from app.features.schedules.schedule_dto import ScheduleCreate
from app.features.schedules.schedule_dto import ScheduleSearchFilter
from app.features.schedules.schedule_dto import ScheduleUpdate
from app.features.schedules.schedule_google_service import ScheduleGoogleService
from app.features.schedules.schedule_service import ScheduleService
from app.infrastructure.models.google_calendar_event_model import GoogleCalendarEventModel


@pytest.fixture
def mock_db_service():
  return MagicMock(spec=ScheduleDBService)


@pytest.fixture
def mock_google_service():
  service = MagicMock(spec=ScheduleGoogleService)
  # Async methods need to be configured properly
  service.create_event = AsyncMock(return_value="mock_google_id")
  service.update_event = AsyncMock()
  service.delete_event = AsyncMock()
  return service


@pytest.fixture
def mock_embedding_service():
  service = MagicMock(spec=EmbeddingService)
  service.embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
  # Property mock
  type(service).model_name = PropertyMock(return_value="gemini-embedding-001")
  return service


@pytest.fixture
def schedule_service(mock_db_service, mock_google_service, mock_embedding_service):
  return ScheduleService(
    db_service=mock_db_service,
    google_service=mock_google_service,
    embedding_service=mock_embedding_service,
  )


@pytest.mark.asyncio
async def test_create_schedule_success(schedule_service, mock_db_service, mock_google_service, mock_embedding_service):
  """일정 생성 시 구글 캘린더 등록 후 로컬 DB 저장이 정상적으로 수행되는지 검증합니다."""
  # Given
  now = datetime.now(UTC)
  payload = ScheduleCreate(
    google_calendar_id="primary",
    summary="Test Event",
    start_at=now,
    end_at=now + timedelta(hours=1),
  )
  owner_id = "user-123"

  mock_db_model = GoogleCalendarEventModel(
    id=1,
    owner_user_id=owner_id,
    google_calendar_id="primary",
    google_event_id="mock_google_id",
    start_at=now,
    end_at=now + timedelta(hours=1),
    created_at=now,
    updated_at=now,
  )
  mock_db_service.create_schedule.return_value = mock_db_model

  # When
  result = await schedule_service.create_schedule(owner_user_id=owner_id, payload=payload)

  # Then
  mock_google_service.create_event.assert_awaited_once_with(calendar_id="primary", payload=payload)

  # 임베딩 생성 시 전달된 텍스트 계약(Contract) 검증
  expected_text = f"제목 : {payload.summary}\n설명 : \n시작시간 : {payload.start_at}\n종료시간 : {payload.end_at}"
  mock_embedding_service.embedding.assert_awaited_once_with(expected_text)

  mock_db_service.create_schedule.assert_called_once_with(
    owner_user_id=owner_id,
    google_event_id="mock_google_id",
    payload=payload,
    model_name="gemini-embedding-001",
    embedding=[0.1, 0.2, 0.3],
  )
  assert result == mock_db_model


def test_read_schedules_uses_only_db(schedule_service, mock_db_service, mock_google_service):
  """조회 시 Single Source of Truth 원칙에 따라 DB 서비스만 호출하는지 검증합니다."""
  # Given
  filters = ScheduleSearchFilter(keyword="meeting")
  owner_id = "user-123"
  mock_db_service.read_schedules.return_value = []

  # When
  result = schedule_service.read_schedules(owner_user_id=owner_id, filters=filters)

  # Then
  # 구글 API는 절대 호출되어서는 안 됨
  mock_google_service.create_event.assert_not_called()
  mock_google_service.update_event.assert_not_called()
  mock_google_service.delete_event.assert_not_called()

  # DB 조회 서비스만 호출되어야 함
  mock_db_service.read_schedules.assert_called_once_with(owner_user_id=owner_id, filters=filters)
  assert result == []


@pytest.mark.asyncio
async def test_update_schedule_success(schedule_service, mock_db_service, mock_google_service, mock_embedding_service):
  """일정 수정 시 DB 식별 기반으로 원격과 로컬을 동기화하는지 검증합니다."""
  # Given
  owner_id = "user-123"
  db_id = 1
  payload = ScheduleUpdate(summary="Updated Event")

  now = datetime.now(UTC)
  mock_db_model = GoogleCalendarEventModel(
    id=db_id,
    owner_user_id=owner_id,
    google_calendar_id="primary",
    google_event_id="mock_google_id",
    start_at=now,
    end_at=now + timedelta(hours=1),
    created_at=now,
    updated_at=now,
  )
  mock_db_service.get_schedule.return_value = mock_db_model
  mock_db_service.update_schedule.return_value = mock_db_model

  # When
  await schedule_service.update_schedule(owner_user_id=owner_id, db_id=db_id, payload=payload)

  # Then
  mock_google_service.update_event.assert_awaited_once_with(
    calendar_id="primary",
    google_event_id="mock_google_id",
    payload=payload,
  )

  # 임베딩 재생성 시 전달된 텍스트 계약(Contract) 검증
  expected_text = f"제목 : {payload.summary}\n설명 : \n시작시간 : {mock_db_model.start_at}\n종료시간 : {mock_db_model.end_at}"
  mock_embedding_service.embedding.assert_awaited_once_with(expected_text)

  mock_db_service.update_schedule.assert_called_once_with(
    mock_db_model,
    payload,
    model_name="gemini-embedding-001",
    updated_embedding=[0.1, 0.2, 0.3],
  )


@pytest.mark.asyncio
async def test_delete_schedule_success(schedule_service, mock_db_service, mock_google_service):
  """일정 삭제 시 원격 삭제 후 로컬 소프트 삭제를 수행하는지 검증합니다."""
  # Given
  owner_id = "user-123"
  db_id = 1

  now = datetime.now(UTC)
  mock_db_model = GoogleCalendarEventModel(
    id=db_id,
    owner_user_id=owner_id,
    google_calendar_id="primary",
    google_event_id="mock_google_id",
    start_at=now,
    end_at=now + timedelta(hours=1),
    created_at=now,
    updated_at=now,
  )
  mock_db_service.get_schedule.return_value = mock_db_model

  # When
  await schedule_service.delete_schedule(owner_user_id=owner_id, db_id=db_id)

  # Then
  mock_google_service.delete_event.assert_awaited_once_with(
    calendar_id="primary",
    google_event_id="mock_google_id",
  )
  mock_db_service.delete_schedule.assert_called_once_with(mock_db_model)


@pytest.mark.asyncio
async def test_create_schedule_invalid_model_fails(schedule_service, mock_db_service, mock_google_service, mock_embedding_service):
  """허용되지 않은 모델 이름을 사용하는 경우 ValueError가 발생하는지 검증합니다."""
  # Given
  from sqlmodel import Session

  from app.features.schedules.schedule_db_service import ScheduleDBService

  # 실제 DB 서비스를 사용하여 검증 로직을 태우기 위해 세션 모킹
  real_db_service = ScheduleDBService(session=MagicMock(spec=Session))
  schedule_service._db_service = real_db_service

  now = datetime.now(UTC)
  payload = ScheduleCreate(
    google_calendar_id="primary",
    summary="Invalid Model Test",
    start_at=now,
    end_at=now + timedelta(hours=1),
  )

  # unknown 모델명 설정 (EmbeddingService 모킹)
  type(mock_embedding_service).model_name = PropertyMock(return_value="unknown-model")

  # When & Then
  with pytest.raises(ValueError, match="Invalid embedding model name"):
    await schedule_service.create_schedule(owner_user_id="user-123", payload=payload)


@pytest.mark.asyncio
async def test_create_schedule_without_embedding_service_skips_embedding():
  """임베딩 비활성화 시 임베딩 없이 일정 생성이 가능해야 합니다."""
  mock_db_service = MagicMock(spec=ScheduleDBService)
  mock_google_service = MagicMock(spec=ScheduleGoogleService)
  mock_google_service.create_event = AsyncMock(return_value="mock_google_id")
  type(mock_google_service).is_connected = PropertyMock(return_value=True)

  service = ScheduleService(
    db_service=mock_db_service,
    google_service=mock_google_service,
    embedding_service=None,
  )

  now = datetime.now(UTC)
  payload = ScheduleCreate(
    google_calendar_id="primary",
    summary="임베딩 없는 일정",
    start_at=now,
    end_at=now + timedelta(hours=1),
  )

  await service.create_schedule(owner_user_id="user-123", payload=payload)

  mock_db_service.create_schedule.assert_called_once_with(
    owner_user_id="user-123",
    google_event_id="mock_google_id",
    payload=payload,
    model_name=None,
    embedding=None,
  )


@pytest.mark.asyncio
async def test_update_schedule_without_embedding_service_skips_embedding():
  """임베딩 비활성화 시 임베딩 없이 일정 수정이 가능해야 합니다."""
  mock_db_service = MagicMock(spec=ScheduleDBService)
  mock_google_service = MagicMock(spec=ScheduleGoogleService)
  mock_google_service.update_event = AsyncMock()
  type(mock_google_service).is_connected = PropertyMock(return_value=True)

  service = ScheduleService(
    db_service=mock_db_service,
    google_service=mock_google_service,
    embedding_service=None,
  )

  now = datetime.now(UTC)
  db_model = GoogleCalendarEventModel(
    id=1,
    owner_user_id="user-123",
    google_calendar_id="primary",
    google_event_id="mock_google_id",
    summary="기존 일정",
    start_at=now,
    end_at=now + timedelta(hours=1),
    created_at=now,
    updated_at=now,
  )
  payload = ScheduleUpdate(summary="변경된 일정")
  mock_db_service.get_schedule.return_value = db_model

  await service.update_schedule(owner_user_id="user-123", db_id=1, payload=payload)

  mock_db_service.update_schedule.assert_called_once_with(
    db_model,
    payload,
    model_name=None,
    updated_embedding=None,
  )
