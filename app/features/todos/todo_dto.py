from datetime import UTC
from datetime import date
from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from app.api.common.request_entity import TodoPriority
from app.api.common.request_entity import TodoStatus
from app.infrastructure.models.todo_model import TodoModel


class TodoCreate(BaseModel):
  """할일(Todo) 생성용 DTO입니다."""

  title: str = Field(description="할일 제목")
  description: str = Field(default="", description="상세 설명")
  status: TodoStatus = Field(default=TodoStatus.TODO, description="상태: 'TODO' | 'DONE'")
  priority: TodoPriority = Field(default=TodoPriority.NORMAL, description="우선순위: 'urgent' | 'high' | 'normal'")
  project: str = Field(default="", description="프로젝트/태그")
  due_date: date | None = Field(default=None, description="마감일")
  sort_order: int = Field(default=0, description="정렬 순서")

  def to_model(self, owner_user_id: str) -> TodoModel:
    now = datetime.now(UTC)
    return TodoModel(
      owner_user_id=owner_user_id,
      title=self.title,
      description=self.description,
      status=self.status,
      priority=self.priority,
      project=self.project,
      due_date=self.due_date,
      sort_order=self.sort_order,
      created_at=now,
      updated_at=now,
    )


class TodoUpdate(BaseModel):
  """할일(Todo) 수정용 DTO입니다."""

  title: str | None = None
  description: str | None = None
  status: TodoStatus | None = None
  priority: TodoPriority | None = None
  project: str | None = None
  due_date: date | None = None
  sort_order: int | None = None


class TodoSearchFilter(BaseModel):
  """하이브리드 조회를 위한 필터 DTO입니다."""

  keyword: str | None = Field(default=None, description="검색할 키워드 (Hybrid 검색용)")
  query_vector: list[float] | None = Field(default=None, description="키워드의 임베딩 벡터 (Hybrid 검색용)")
  status: TodoStatus | None = Field(default=None, description="특정 상태 필터")
  priority: TodoPriority | None = Field(default=None, description="특정 우선순위 필터")
  project: str | None = Field(default=None, description="특정 프로젝트 필터")
  limit: int | None = Field(default=None, description="조회 개수 제한")
