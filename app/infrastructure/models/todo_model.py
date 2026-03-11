from __future__ import annotations

from datetime import date
from datetime import datetime

from sqlalchemy import CheckConstraint
from sqlalchemy import Column
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field
from sqlmodel import SQLModel

from app.infrastructure.models.auth_user_model import AuthUserModel  # noqa: F401


class TodoModel(SQLModel, table=True):
  """할일(Todo) 테이블 모델.

  사용자의 할일 목록을 관리합니다.
  - 상태(status): TODO / DONE
  - 우선순위(priority): urgent / high / normal
  - 프로젝트(project): 자유 텍스트 태그
  - 정렬 순서(sort_order): DnD 드래그 앤 드롭 지원
  """

  __tablename__: str = "todos"  # pyright: ignore[reportAssignmentType, reportIncompatibleVariableOverride]

  __table_args__ = (
    # status 값 제약
    CheckConstraint(
      "status IN ('TODO', 'DONE')",
      name="ck_todos_status",
    ),
    # priority 값 제약
    CheckConstraint(
      "priority IN ('urgent', 'high', 'normal')",
      name="ck_todos_priority",
    ),
    # 사용자별 상태 조회 (소프트 삭제 제외)
    Index(
      "ix_todos_owner_status",
      "owner_user_id",
      "status",
      postgresql_where=text("deleted_at IS NULL"),
    ),
    # 사용자별 상태+정렬순서 (DnD 목록 쿼리 최적화)
    Index(
      "ix_todos_owner_status_sort",
      "owner_user_id",
      "status",
      "sort_order",
      postgresql_where=text("deleted_at IS NULL"),
    ),
  )

  # PK
  id: int | None = Field(
    default=None,
    sa_column=Column(Integer, primary_key=True, autoincrement=True),
  )

  # 소유자 (Supabase Auth 사용자)
  owner_user_id: str = Field(
    sa_column=Column(
      UUID(as_uuid=False),
      ForeignKey("auth.users.id", ondelete="CASCADE"),
      nullable=False,
      index=True,
    ),
    description="소유자 Supabase Auth UUID(auth.users.id)",
  )

  # 핵심 필드
  title: str = Field(
    sa_column=Column(Text, nullable=False),
    description="할일 제목 (필수)",
  )
  description: str = Field(
    default="",
    sa_column=Column(Text, nullable=False, server_default=text("''")),
    description="상세 설명 (선택)",
  )
  status: str = Field(
    default="TODO",
    sa_column=Column(String(16), nullable=False, server_default=text("'TODO'")),
    description="상태: 'TODO' | 'DONE'",
  )
  priority: str = Field(
    default="normal",
    sa_column=Column(String(16), nullable=False, server_default=text("'normal'")),
    description="우선순위: 'urgent' | 'high' | 'normal'",
  )

  # 부가 필드
  project: str = Field(
    default="",
    sa_column=Column(Text, nullable=False, server_default=text("''")),
    description="프로젝트/태그 (예: '프로젝트 알파', '디자인팀')",
  )
  due_date: date | None = Field(
    default=None,
    sa_column=Column(Date, nullable=True),
    description="마감일 (선택, 향후 확장)",
  )
  sort_order: int = Field(
    default=0,
    sa_column=Column(Integer, nullable=False, server_default=text("0")),
    description="목록 내 정렬 순서 (DnD 지원)",
  )

  # 타임스탬프
  created_at: datetime = Field(
    sa_column=Column(
      DateTime(timezone=True),
      nullable=False,
      server_default=text("timezone('utc', now())"),
    ),
  )
  updated_at: datetime = Field(
    sa_column=Column(
      DateTime(timezone=True),
      nullable=False,
      server_default=text("timezone('utc', now())"),
    ),
  )
  deleted_at: datetime | None = Field(
    default=None,
    sa_column=Column(DateTime(timezone=True), nullable=True),
    description="소프트 삭제 타임스탬프",
  )

  # 벡터 검색용 임베딩 참조 컬럼
  embedding_id: int | None = Field(
    default=None,
    sa_column=Column(
      Integer,
      ForeignKey("event_embeddings_base.id", ondelete="SET NULL"),
      nullable=True,
    ),
    description="임베딩 베이스 테이블 참조 ID",
  )
