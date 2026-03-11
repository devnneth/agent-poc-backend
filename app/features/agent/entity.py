from enum import StrEnum

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

from app.api.common.request_entity import TodoStatus
from app.api.common.response_entity import AgentResponseSSECategory


class BaseStrEnum(StrEnum):
  @classmethod
  def has_value(cls, value: str) -> bool:
    return value in cls._value2member_map_


class IntentType(BaseStrEnum):
  GENERAL = "general"
  SCHEDULE = "schedule"
  TODO = "todo"
  MEMO = "memo"


class ActionType(BaseStrEnum):
  ADD = "add"
  UPDATE = "update"
  DELETE = "delete"
  SEARCH = "search"


class HITLResultType(BaseStrEnum):
  APPROVE = "approve"
  REJECT = "reject"


class DeleteResultType(BaseStrEnum):
  SUCCESS = "success"
  ALREADY_DELETED = "already_deleted"
  NOT_FOUND = "not_found"
  FAILED = "failed"


class UpdateResultType(BaseStrEnum):
  SUCCESS = "success"
  NOT_FOUND = "not_found"
  FAILED = "failed"


class RouterIntent(BaseStrEnum):
  """루트 라우터가 선택할 수 있는 노드/서브그래프 이름"""

  SCHEDULE_AGENT = "schedule_agent"
  TODO_AGENT = "todo_agent"
  MEMO_AGENT = "memo_agent"
  GENERAL_CONVERSATION = "general_conversation_node"


class AgentNodeName(BaseStrEnum):
  # --- Router Agent Nodes ---
  ROOT_INTENT = "root_intent_node"
  GENERAL_CONVERSATION = "general_conversation_node"

  # --- Router Agent Sub-Graphs ---
  SCHEDULE_AGENT = "schedule_agent"
  TODO_AGENT = "todo_agent"
  MEMO_AGENT = "memo_agent"

  # --- Schedule Agent Nodes ---
  CLASSIFY_ACTION = "classify_schedule_action_node"
  EXTRACT_INFO = "extract_information_node"
  CHECK_INFO = "check_information_node"
  INTENT_SHIFT = "intent_shift_node"
  USER_CONFIRM = "user_confirmation_node"
  EXECUTE_TOOL = "execute_tool_node"
  FINAL_RESPONSE = "final_response_node"
  CANCEL_NODE = "cancel_node"


class ScheduleExtractedInfo(BaseModel):
  summary: str | None = Field(default=None, description="일정 제목")
  start_at: str | None = Field(
    default=None,
    description="시작 일시 (ISO 8601 형식). '올해', '이번달' 같은 상대적 시간은 반드시 프롬프트의 '현재 기준 일시' 연도(Year)/월(Month)을 추출 기준일로 삼아야 합니다 (예: 2026년 기준이면 2026-01-01T00:00:00). 절대 과거의 기본 학습 연도를 임의로 사용하지 마세요. 알 수 없으면 None 반환.",
  )
  end_at: str | None = Field(
    default=None,
    description="종료 일시 (ISO 8601 형식). 위와 동일하게 '현재 기준 일시' 연도/월 등을 철저히 계산한 정확한 날짜로 반환하세요. 알 수 없거나 미정이면 반드시 None 반환.",
  )
  schedule_id: int | None = Field(
    default=None,
    description="수정/삭제 대상 일정의 고유 ID. 시스템 내부 식별자이므로 사용자에게 직접 묻거나 요청하지 마세요. 사용자의 입력에 명시적인 숫자 ID가 포함된 경우에만 추출합니다.",
  )
  description: str | None = Field(default=None, description="상세 설명")
  color_id: str | None = Field(default=None, description="색상 ID")
  query: str | None = Field(default=None, description="조회 시 사용할 검색 키워드")


class TodoExtractedInfo(BaseModel):
  title: str | None = Field(default=None, description="할일 제목")
  description: str | None = Field(default=None, description="상세 설명")
  status: str | None = Field(default=None, description="상태 (TODO, DONE)")
  priority: str | None = Field(default=None, description="우선순위 (urgent, high, normal)")
  project: str | None = Field(default=None, description="프로젝트/카테고리")
  todo_id: int | None = Field(default=None, description="할일 고유 ID (수정/삭제 시)")
  query: str | None = Field(default=None, description="검색 키워드")

  @field_validator("status", mode="before")
  @classmethod
  def normalize_status(cls, value: object) -> object:
    """HITL 응답의 bool status를 기존 TodoStatus 문자열로 복원합니다."""
    return deserialize_todo_status(value)


class MemoExtractedInfo(BaseModel):
  title: str | None = Field(default=None, description="메모 제목")
  content: str | None = Field(default=None, description="메모 본문")
  memo_id: int | None = Field(default=None, description="메모 고유 ID (수정/삭제 시)")
  query: str | None = Field(default=None, description="검색 키워드")


class SlotCheckResult(BaseModel):
  """check_information_node에서 LLM이 반환하는 슬롯 충족 여부 결과 모델"""

  is_sufficient: bool = Field(description="액션 실행에 필요한 정보가 모두 충족되면 true")
  missing_message: str | None = Field(default=None, description="is_sufficient=false일 때 사용자에게 전달할 안내 문구")


class IntentShiftResult(BaseModel):
  """interrupt 재개 후 의도 전환 여부 판별 결과"""

  is_shifted: bool = Field(description="사용자가 기존 흐름과 다른 새로운 의도를 표현하면 true")


class HITLInterruptData(BaseModel):
  """사용자 확인이 필요한 경우 interrupt에 전달할 데이터 모델"""

  category: AgentResponseSSECategory = Field(description="이벤트 유형")
  message: str = Field(description="사용자에게 보여줄 메시지")
  intent: IntentType | None = Field(default=None, description="현재 인터럽트가 속한 의도")
  action: ActionType | None = Field(default=None, description="수행할 액션")
  schedule_slots: ScheduleExtractedInfo | None = Field(default=None, description="추출된 일정 정보")
  todo_slots: TodoExtractedInfo | None = Field(default=None, description="추출된 할일 정보")
  memo_slots: MemoExtractedInfo | None = Field(default=None, description="추출된 메모 정보")


def deserialize_todo_status(value: object) -> object:
  """bool 또는 Enum 상태값을 내부 표준 문자열(TODO/DONE)로 정규화합니다."""
  if isinstance(value, bool):
    return TodoStatus.DONE.value if value else TodoStatus.TODO.value
  if isinstance(value, TodoStatus):
    return value.value
  return value


def serialize_todo_status_for_hitl(value: object) -> bool | None:
  """HITL payload 전송 시 TODO/DONE 상태를 False/True로 직렬화합니다."""
  normalized = deserialize_todo_status(value)
  if normalized is None:
    return None
  if normalized == TodoStatus.TODO.value:
    return False
  if normalized == TodoStatus.DONE.value:
    return True
  raise ValueError(f"지원하지 않는 todo status 값입니다: {value!r}")


def build_hitl_interrupt_payload(interrupt_data: HITLInterruptData) -> dict[str, object]:
  """todo_slots.status를 HITL 계약에 맞춰 bool로 변환한 payload를 생성합니다."""
  payload = interrupt_data.model_dump(exclude_none=True)
  todo_slots = payload.get("todo_slots")
  if isinstance(todo_slots, dict) and "status" in todo_slots:
    todo_slots["status"] = serialize_todo_status_for_hitl(todo_slots.get("status"))
  return payload
