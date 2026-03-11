from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import Text
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field
from sqlmodel import SQLModel

from app.infrastructure.models.auth_user_model import AuthUserModel  # noqa: F401


class MemoModel(SQLModel, table=True):
  """메모(Memo) 테이블 모델.

  사용자의 메모를 관리합니다.
  - 제목(title): 기본값 '제목 없는 메모'
  - 본문(content): 마크다운/플레인텍스트 지원
  - 전문 검색: title + content GIN 인덱스 (마이그레이션에서 별도 생성)
  """

  __tablename__: str = "memos"  # pyright: ignore[reportAssignmentType, reportIncompatibleVariableOverride]

  __table_args__ = (
    # 사용자별 최신순 조회 (소프트 삭제 제외)
    Index(
      "ix_memos_owner_updated",
      "owner_user_id",
      "updated_at",
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
    default="제목 없는 메모",
    sa_column=Column(Text, nullable=False, server_default=text("'제목 없는 메모'")),
    description="메모 제목",
  )
  content: str = Field(
    default="",
    sa_column=Column(Text, nullable=False, server_default=text("''")),
    description="메모 본문 (마크다운/플레인텍스트)",
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
