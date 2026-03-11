import json
from datetime import datetime
from datetime import timedelta
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.core.config.settings import Settings
from app.features.agent.entity import HITLResultType
from app.features.agent.entity import MemoExtractedInfo
from app.features.agent.entity import ScheduleExtractedInfo
from app.features.agent.entity import TodoExtractedInfo
from app.features.agent.settings import AGENT_MODEL_SETTINGS as AMS
from app.features.llm.llm_service import LLMServiceFactory
from app.infrastructure.common.exceptions import LLMError


def apply_nostream(runnable, node_settings):
  """전역 설정에 따라 스트리밍 이벤트를 무시할 수 있도록 nostream 태그를 추가합니다."""
  if not node_settings.get("streaming", True):
    return runnable.with_config(tags=["nostream"])
  return runnable


def extract_enum_from_response[E](enum_cls: type[E], response: object, default: E | None = None) -> E | None:
  """LLM 응답 response에서 Enum 값을 안전하게 추출합니다.

  Args:
    enum_cls: has_value() 메서드를 가진 BaseStrEnum 서브클래스.
    response:  LLM 응답 객체 (AIMessage 등). .content 속성에서 값을 추출합니다.
    default:  유효한 Enum 값이 없을 때 반환할 기본값.

  Returns:
    enum_cls(content) 또는 default.
  """
  # Structured Output은 AIMessage.content 외에도 Enum, dict, list 형태로 반환될 수 있습니다.
  if isinstance(response, enum_cls):
    return response

  candidates: list[object] = []

  if isinstance(response, dict):
    candidates.extend(response.get("values", []))
    candidates.extend(response.values())
  else:
    content = getattr(response, "content", None)
    if content is not None:
      candidates.append(content)

  for candidate in candidates:
    if isinstance(candidate, enum_cls):
      return candidate
    if isinstance(candidate, str):
      cleaned_content = candidate.strip().lower()
      if enum_cls.has_value(cleaned_content):  # type: ignore[attr-defined]
        return enum_cls(cleaned_content)  # type: ignore[call-arg]
  return default


def get_llm(node_name: str, config: RunnableConfig):
  """노드명과 config를 받아 LLM 인스턴스를 반환하는 헬퍼 함수"""
  provider = AMS[node_name].get("provider")

  if not provider:
    raise LLMError(f"'{node_name}' 노드의 provider 설정이 존재하지 않습니다.")

  return LLMServiceFactory.get_service(provider).get_model_for_node(node_name, callbacks=config.get("callbacks"))


def fill_end_at(schedule_slots: ScheduleExtractedInfo) -> ScheduleExtractedInfo:
  """end_at이 없거나 start_at과 충돌할 때 자동으로 보정합니다.

  규칙:
  1. start_at이 있고 end_at이 None → end_at = start_at + 1시간
  2. start_at과 end_at이 모두 있고 end_at <= start_at → end_at = start_at + 1시간
  """
  if not schedule_slots.start_at:
    return schedule_slots

  try:
    start = datetime.fromisoformat(schedule_slots.start_at)
  except ValueError:
    return schedule_slots

  need_fill = schedule_slots.end_at is None
  if not need_fill and schedule_slots.end_at:
    try:
      end = datetime.fromisoformat(schedule_slots.end_at)
      need_fill = end <= start
    except ValueError:
      need_fill = True

  if need_fill:
    duration = timedelta(hours=Settings().SCHEDULE_DEFAULT_DURATION_HOURS)
    new_end = (start + duration).isoformat()
    return schedule_slots.model_copy(update={"end_at": new_end})

  return schedule_slots


def _get_confirmation_content(res: object) -> str:
  """interrupt 재개 응답에서 마지막 메시지 본문을 문자열로 추출합니다."""
  last_msg = (res.get("messages") or [{}])[-1] if isinstance(res, dict) else res
  return getattr(last_msg, "content", last_msg.get("content", "") if isinstance(last_msg, dict) else str(last_msg or ""))


def _load_confirmation_payload(res: object) -> dict[str, Any] | None:
  """사용자 확인 응답이 JSON 문자열이면 dict로 파싱합니다."""
  content = _get_confirmation_content(res)
  try:
    parsed = json.loads(content)
    if isinstance(parsed, dict):
      return parsed
  except (json.JSONDecodeError, TypeError, ValueError):
    pass
  return None


def parse_user_confirmed(res: object) -> HITLResultType:
  """사용자 확인 응답에서 승인/거절 여부만 파싱합니다."""
  parsed = _load_confirmation_payload(res)
  if parsed is not None:
    confirmed_val = str(parsed.get("user_confirmed", "")).strip().lower()
    return HITLResultType.APPROVE if confirmed_val == HITLResultType.APPROVE.value else HITLResultType.REJECT

  content = _get_confirmation_content(res)
  is_approved = str(content).strip().lower() == HITLResultType.APPROVE.value
  return HITLResultType.APPROVE if is_approved else HITLResultType.REJECT


def _parse_confirmation_slots[T: ScheduleExtractedInfo | TodoExtractedInfo | MemoExtractedInfo](
  res: object,
  model_cls: type[T],
  nested_key: str,
) -> tuple[HITLResultType, T | None]:
  """사용자 승인 결과와 도메인별 수정 정보를 함께 파싱합니다."""
  user_confirmed = parse_user_confirmed(res)
  parsed = _load_confirmation_payload(res)
  if parsed is None:
    return user_confirmed, None

  nested_data = parsed.get(nested_key)
  data_to_parse = nested_data if isinstance(nested_data, dict) else parsed
  slot_data = {k: v for k, v in data_to_parse.items() if k in model_cls.model_fields}
  updated_slots = model_cls(**slot_data) if slot_data else None
  return user_confirmed, updated_slots


def parse_todo_confirmation(res: object) -> tuple[HITLResultType, TodoExtractedInfo | None]:
  """할일 사용자 확인 응답에서 승인 여부와 수정된 todo 정보를 파싱합니다."""
  return _parse_confirmation_slots(res, TodoExtractedInfo, "todo_slots")


def parse_memo_confirmation(res: object) -> tuple[HITLResultType, MemoExtractedInfo | None]:
  """메모 사용자 확인 응답에서 승인 여부와 수정된 memo 정보를 파싱합니다."""
  return _parse_confirmation_slots(res, MemoExtractedInfo, "memo_slots")


def parse_schedule_confirmation(res: object) -> tuple[HITLResultType, ScheduleExtractedInfo | None]:
  """일정 사용자 확인 응답에서 승인 여부와 수정된 schedule 정보를 파싱합니다."""
  return _parse_confirmation_slots(res, ScheduleExtractedInfo, "schedule_slots")
