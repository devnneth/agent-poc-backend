from datetime import datetime
from unittest.mock import MagicMock

import pytest

from app.features.memos.memo_service import MemoService
from app.features.schedules.schedule_db_service import ScheduleDBService
from app.features.schedules.schedule_google_service import ScheduleGoogleService
from app.features.schedules.schedule_service import ScheduleService
from app.features.todos.todo_service import TodoService


@pytest.fixture
def schedule_service():
  """테스트를 위한 최소한의 ScheduleService 인스턴스를 생성합니다."""
  return ScheduleService(
    db_service=MagicMock(spec=ScheduleDBService),
    google_service=MagicMock(spec=ScheduleGoogleService),
    embedding_service=None,
  )


def test_format_schedule_for_embedding_standard(schedule_service):
  """표준적인 입력에 대해 기대하는 포맷이 출력되는지 검증합니다."""
  # Given
  summary = "주간 회의"
  description = "팀별 주간 업무 보고"
  start_at = datetime(2025, 2, 25, 10, 0)
  end_at = datetime(2025, 2, 25, 11, 0)

  # When
  result = ScheduleService.format_schedule_for_embedding(summary=summary, description=description, start_at=start_at, end_at=end_at)

  # Then
  expected = "제목 : 주간 회의\n설명 : 팀별 주간 업무 보고\n시작시간 : 2025-02-25 10:00:00\n종료시간 : 2025-02-25 11:00:00"
  assert result == expected


def test_format_schedule_for_embedding_with_none_values(schedule_service):
  """None 값이 포함된 경우 빈 문자열로 안전하게 처리되는지 검증합니다."""
  # Given
  summary = "제목만 있는 일정"
  description = None
  start_at = datetime(2025, 2, 25, 10, 0)
  end_at = datetime(2025, 2, 25, 11, 0)

  # When
  result = ScheduleService.format_schedule_for_embedding(summary=summary, description=description, start_at=start_at, end_at=end_at)

  # Then
  expected = "제목 : 제목만 있는 일정\n설명 : \n시작시간 : 2025-02-25 10:00:00\n종료시간 : 2025-02-25 11:00:00"
  assert result == expected


def test_format_schedule_for_embedding_all_empty(schedule_service):
  """모든 필드가 비어있거나 None인 경우의 동작을 검증합니다."""
  # Given
  summary = None
  description = ""
  start_at = None
  end_at = None

  # When
  result = ScheduleService.format_schedule_for_embedding(summary=summary, description=description, start_at=start_at, end_at=end_at)

  # Then
  expected = "제목 : \n설명 : \n시작시간 : None\n종료시간 : None"
  assert result == expected


def test_format_todo_for_embedding():
  """Todo 포맷이 반환되는지 검증합니다."""
  # Given
  title = "API 개발"
  description = "임베딩 API 구현"
  status = "TODO"
  priority = "HIGH"
  project = "agent-poc-backend"

  # When
  result = TodoService.format_todo_for_embedding(title=title, description=description, status=status, priority=priority, project=project)

  # Then
  expected = "제목 : API 개발\n설명 : 임베딩 API 구현\n상태 : TODO\n우선순위 : HIGH\n프로젝트 : gent-poc-backend"
  assert result == expected


def test_format_memo_for_embedding():
  """Memo 포맷이 반환되는지 검증합니다."""
  # Given
  title = "회의록"
  content = "오늘의 핵심 안건은 API 설계입니다."

  # When
  result = MemoService.format_memo_for_embedding(title=title, content=content)

  # Then
  expected = "제목 : 회의록\n내용 : 오늘의 핵심 안건은 API 설계입니다."
  assert result == expected
