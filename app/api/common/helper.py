from collections.abc import Mapping
from typing import Any

from app.features.agent.entity import HITLInterruptData


def extract_interrupt(data: Mapping[str, Any]) -> tuple[bool, HITLInterruptData | str | dict[str, Any]]:
  """astream_events v2 이벤트의 data에서 interrupt 정보를 추출합니다.

  LangGraph astream_events v2에서 __interrupt__는 두 가지 위치에 포함될 수 있습니다:
  - data["__interrupt__"]          : 최상위에 직접 포함
  - data["chunk"]["__interrupt__"] : chunk 딕셔너리 안에 중첩

  Args:
    data: astream_events 이벤트의 data 딕셔너리

  Returns:
    (is_interrupt, info) 튜플
      - is_interrupt: 인터럽트 여부
      - info: 인터럽트 정보 (HITLInterruptData 객체 또는 메시지 문자열)
  """
  chunk_data = data.get("chunk")
  interrupt_data = data.get("__interrupt__") or (chunk_data.get("__interrupt__") if isinstance(chunk_data, dict) else None)

  if not interrupt_data:
    return False, ""

  # interrupt_data는 Interrupt 객체의 튜플 또는 리스트: (Interrupt(value=...), ...)
  try:
    info = interrupt_data[0].value if hasattr(interrupt_data, "__getitem__") and len(interrupt_data) > 0 else ""

    if isinstance(info, dict):
      try:
        return True, HITLInterruptData(**info)
      except Exception:
        return True, info

    return True, info
  except (AttributeError, IndexError):
    return True, ""


def extract_content(data: Mapping[str, Any]) -> str:
  """astream_events v2 이벤트의 data에서 content를 추출합니다.

  Args:
    data: astream_events 이벤트의 data 딕셔너리

  Returns:
    추출된 텍스트 내용 (없으면 빈 문자열)
  """
  chunk = data.get("chunk")
  if not chunk:
    return ""

  # chunk가 dict 또는 LangChain 객체일 수 있으므로 두 경우 모두 지원
  content = getattr(chunk, "content", None) if not isinstance(chunk, dict) else chunk.get("content")
  if not content:
    return ""

  # list 형태의 content 대응 (멀티모달 등)
  if isinstance(content, list):
    return "".join([c.get("text", "") if isinstance(c, dict) else str(c) for c in content])

  return str(content)
