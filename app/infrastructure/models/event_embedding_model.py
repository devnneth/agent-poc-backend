from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import text
from sqlmodel import Field
from sqlmodel import SQLModel


class EventEmbeddingBaseModel(SQLModel, table=True):
  """
  이벤트 임베딩의 공통 식별자와 메타 정보를 담당하는 베이스 테이블.
  GoogleCalendarEventModel 에서는 이 모델의 id만 참조합니다.
  """

  __tablename__: str = "event_embeddings_base"  # type: ignore

  id: int | None = Field(
    default=None,
    sa_column=Column(Integer, primary_key=True, autoincrement=True),
  )

  model_name: str = Field(
    sa_column=Column(String(64), nullable=False, index=True),
    description="사용한 임베딩 모델명 (예: custom, openai, gemini)",
  )

  dimension: int = Field(
    sa_column=Column(Integer, nullable=False),
    description="임베딩 벡터 차원 수",
  )

  created_at: datetime | None = Field(
    default=None,
    sa_column=Column(
      DateTime(timezone=True),
      nullable=False,
      server_default=text("timezone('utc', now())"),
    ),
  )


class EventEmbedding1024Model(SQLModel, table=True):
  """1024 차원 벡터 레코드를 저장하는 전용 테이블"""

  __tablename__: str = "event_embeddings_1024"  # type: ignore

  id: int | None = Field(
    default=None,
    sa_column=Column(
      Integer,
      ForeignKey("event_embeddings_base.id", ondelete="CASCADE"),
      primary_key=True,
    ),
    description="베이스 테이블의 id와 동일 (1:1 매핑)",
  )

  embedding: list[float] | None = Field(
    default=None,
    sa_column=Column(Vector(1024), nullable=False),
    description="1024 차원 임베딩 벡터",
  )


class EventEmbedding1536Model(SQLModel, table=True):
  """1536 차원 벡터 레코드를 저장하는 전용 테이블 (OpenAI 등)"""

  __tablename__: str = "event_embeddings_1536"  # type: ignore

  id: int | None = Field(
    default=None,
    sa_column=Column(
      Integer,
      ForeignKey("event_embeddings_base.id", ondelete="CASCADE"),
      primary_key=True,
    ),
    description="베이스 테이블의 id와 동일 (1:1 매핑)",
  )

  embedding: list[float] | None = Field(
    default=None,
    sa_column=Column(Vector(1536), nullable=False),
    description="1536 차원 임베딩 벡터",
  )


class EventEmbedding768Model(SQLModel, table=True):
  """768 차원 벡터 레코드를 저장하는 전용 테이블 (Gemini 등)"""

  __tablename__: str = "event_embeddings_768"  # type: ignore

  id: int | None = Field(
    default=None,
    sa_column=Column(
      Integer,
      ForeignKey("event_embeddings_base.id", ondelete="CASCADE"),
      primary_key=True,
    ),
    description="베이스 테이블의 id와 동일 (1:1 매핑)",
  )

  embedding: list[float] | None = Field(
    default=None,
    sa_column=Column(Vector(768), nullable=False),
    description="768 차원 임베딩 벡터",
  )
