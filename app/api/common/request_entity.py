from datetime import datetime
from enum import StrEnum
from typing import Annotated
from typing import Literal

from pydantic import BaseModel
from pydantic import Field


class TodoStatus(StrEnum):
  TODO = "TODO"
  DONE = "DONE"


class TodoPriority(StrEnum):
  URGENT = "urgent"
  HIGH = "high"
  NORMAL = "normal"


class BaseEmbeddingPayload(BaseModel):
  entity: Literal["GoogleCalendarEventModel", "TodoModel", "MemoModel"]


class GoogleCalendarPayload(BaseEmbeddingPayload):
  entity: Literal["GoogleCalendarEventModel"]
  summary: str | None = None
  description: str | None = None
  start_at: datetime
  end_at: datetime


class TodoPayload(BaseEmbeddingPayload):
  entity: Literal["TodoModel"]
  title: str
  description: str = ""
  status: TodoStatus = TodoStatus.TODO
  priority: TodoPriority = TodoPriority.NORMAL
  project: str = ""


class MemoPayload(BaseEmbeddingPayload):
  entity: Literal["MemoModel"]
  title: str = "제목 없는 메모"
  content: str = ""


LLMEmbeddingRequest = Annotated[GoogleCalendarPayload | TodoPayload | MemoPayload, Field(discriminator="entity")]


class AgentChatRequest(BaseModel):
  """에이전트 채팅 요청 DTO"""

  user_id: str = Field(..., examples=["user-8888"])
  session_id: str = Field(..., examples=["session-abc-123"])
  calendar_id: str | None = Field(default=None, examples=["calendar-abc-123"])
  message: str = Field(..., min_length=1, examples=["안녕하세요"])
  language: str = Field("ko", min_length=1, examples=["ko"])
  minutes_offset: int = Field(540, description="분 단위 시간 오프셋")
  google_calendar_token: str | None = Field(default=None, examples=["dummy_google_access_token"])


class AgentConfigurable(BaseModel):
  """에이전트 실행 시 전달되는 설정 모델"""

  user_id: str = Field(..., description="사용자 식별자")
  session_id: str = Field(..., description="세션 식별자")
  calendar_id: str | None = Field(default=None, description="캘린더 식별자")
  thread_id: str = Field(..., description="LangGraph 스레드 식별자")
  language: str = Field("ko", description="응답 언어")
  minutes_offset: int = Field(540, description="분 단위 시간 오프셋")
