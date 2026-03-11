from enum import StrEnum
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class SSEType(StrEnum):
  START = "start"
  DATA = "data"
  END = "end"


class SSECategory(StrEnum):
  THINKING = "thinking"
  TOOL = "tool"
  MESSAGE = "message"
  ERROR = "error"
  RAW = "raw"
  NONE = ""


class SSEStatus(StrEnum):
  START = "start"
  ING = "ing"
  END = "end"
  NONE = ""


class SSEPayload(BaseModel):
  type: SSEType
  category: SSECategory = SSECategory.NONE
  status: SSEStatus = SSEStatus.NONE
  content: str
  metadata: dict[str, Any] = Field(default_factory=dict)
  model_config = ConfigDict(
    use_enum_values=True,
    populate_by_name=True,
  )
