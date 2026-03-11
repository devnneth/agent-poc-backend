from __future__ import annotations

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field
from sqlmodel import SQLModel


class AuthUserModel(SQLModel, table=True):
  """Supabase Auth의 users 테이블에 대한 스텁 모델입니다.

  이 모델은 다른 모델에서 auth.users를 외래 키로 참조할 때
  SQLAlchemy MetaData가 해당 테이블을 찾지 못하는 오류를 방지하기 위해 존재합니다.
  """

  __tablename__: str = "users"  # pyright: ignore[reportAssignmentType, reportIncompatibleVariableOverride]
  __table_args__ = {"schema": "auth"}

  id: str = Field(
    sa_column=Column(UUID(as_uuid=False), primary_key=True),
    description="Supabase Auth User UUID",
  )
