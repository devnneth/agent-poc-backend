from enum import StrEnum
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class CommonResponse(BaseModel):
  """API 공통 응답 스키마 (Domain Entity)"""

  result: Any | None
  message: str = ""
  error: bool = False
  status: int
  code: str | None = None
  detail: Any | None = None

  model_config = ConfigDict(from_attributes=True)


class AgentResponseSSEType(StrEnum):
  START = "start"
  DATA = "data"
  END = "end"


class AgentResponseSSECategory(StrEnum):
  THINKING = "thinking"
  TOOL = "tool"
  MESSAGE = "message"
  HITL = "hitl"
  ERROR = "error"
  NONE = ""


class AgentResponseSSEStatus(StrEnum):
  START = "start"
  ING = "ing"
  END = "end"
  NONE = ""


class AgentResponseSSEPayload(BaseModel):
  """SSE 응답 페이로드 스키마. type이 가장 먼저 오도록 필드 순서가 중요합니다."""

  type: AgentResponseSSEType
  category: AgentResponseSSECategory = AgentResponseSSECategory.NONE
  status: AgentResponseSSEStatus = AgentResponseSSEStatus.NONE
  content: Any
  metadata: dict[str, Any] = Field(default_factory=dict)
