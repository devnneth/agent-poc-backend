import json
from unittest.mock import MagicMock

from app.api.common.request_entity import TodoStatus
from app.api.common.response_entity import AgentResponseSSECategory
from app.features.agent.entity import ActionType
from app.features.agent.entity import HITLInterruptData
from app.features.agent.entity import HITLResultType
from app.features.agent.entity import IntentType
from app.features.agent.entity import MemoExtractedInfo
from app.features.agent.entity import TodoExtractedInfo
from app.features.agent.entity import build_hitl_interrupt_payload
from app.features.agent.helpers.graph_helpers import parse_memo_confirmation
from app.features.agent.helpers.graph_helpers import parse_schedule_confirmation
from app.features.agent.helpers.graph_helpers import parse_todo_confirmation
from app.features.agent.helpers.graph_helpers import parse_user_confirmed


def test_parse_user_confirmed_returns_approve_for_json_payload():
  """JSON 응답에 승인 값이 있으면 approve를 반환해야 합니다."""
  res = {"messages": [MagicMock(content=json.dumps({"user_confirmed": "approve"}))]}

  result = parse_user_confirmed(res)

  assert result == HITLResultType.APPROVE


def test_parse_user_confirmed_returns_reject_for_plain_text_fallback():
  """문자열 응답이 approve가 아니면 reject를 반환해야 합니다."""
  result = parse_user_confirmed("아니오")

  assert result == HITLResultType.REJECT


def test_parse_todo_confirmation_returns_updated_todo_slots():
  """할일 승인 응답에서 수정된 todo 필드를 함께 파싱해야 합니다."""
  res = {
    "messages": [
      MagicMock(
        content=json.dumps(
          {
            "user_confirmed": "approve",
            "todo_slots": {
              "title": "아침 운동하기",
              "priority": "high",
            },
          }
        )
      )
    ]
  }

  user_confirmed, todo_slots = parse_todo_confirmation(res)

  assert user_confirmed == HITLResultType.APPROVE
  assert todo_slots is not None
  assert todo_slots.title == "아침 운동하기"
  assert todo_slots.priority == "high"


def test_parse_todo_confirmation_restores_bool_status_to_todo_status_string():
  """할일 승인 응답의 bool status를 내부 표준 상태 문자열로 복원해야 합니다."""
  res = {
    "messages": [
      MagicMock(
        content=json.dumps(
          {
            "user_confirmed": "approve",
            "todo_slots": {
              "status": True,
            },
          }
        )
      )
    ]
  }

  user_confirmed, todo_slots = parse_todo_confirmation(res)

  assert user_confirmed == HITLResultType.APPROVE
  assert todo_slots is not None
  assert todo_slots.status == TodoStatus.DONE.value


def test_build_hitl_interrupt_payload_serializes_todo_status_as_bool():
  """할일 HITL payload의 status는 True/False로 직렬화되어야 합니다."""
  payload = build_hitl_interrupt_payload(
    HITLInterruptData(
      category=AgentResponseSSECategory.HITL,
      message="확인",
      intent=IntentType.TODO,
      action=ActionType.ADD,
      todo_slots=TodoExtractedInfo(title="운동", status=TodoStatus.TODO),
    )
  )

  todo_slots = payload["todo_slots"]
  assert isinstance(todo_slots, dict)
  assert todo_slots["status"] is False


def test_parse_schedule_confirmation_returns_updated_schedule_slots():
  """일정 승인 응답에서 수정된 schedule 필드를 함께 파싱해야 합니다."""
  res = {
    "messages": [
      MagicMock(
        content=json.dumps(
          {
            "user_confirmed": "approve",
            "schedule_slots": {
              "summary": "팀 회의",
              "start_at": "2026-03-11T10:00:00",
            },
          }
        )
      )
    ]
  }

  user_confirmed, schedule_slots = parse_schedule_confirmation(res)

  assert user_confirmed == HITLResultType.APPROVE
  assert schedule_slots is not None
  assert schedule_slots.summary == "팀 회의"
  assert schedule_slots.start_at == "2026-03-11T10:00:00"


def test_parse_memo_confirmation_returns_updated_memo_slots():
  """메모 승인 응답에서 수정된 memo 필드를 함께 파싱해야 합니다."""
  res = {
    "messages": [
      MagicMock(
        content=json.dumps(
          {
            "user_confirmed": "approve",
            "memo_slots": {
              "title": "회의 메모",
              "content": "안건 정리",
            },
          }
        )
      )
    ]
  }

  user_confirmed, memo_slots = parse_memo_confirmation(res)

  assert user_confirmed == HITLResultType.APPROVE
  assert memo_slots is not None
  assert memo_slots == MemoExtractedInfo(title="회의 메모", content="안건 정리")
