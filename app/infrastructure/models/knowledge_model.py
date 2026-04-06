from __future__ import annotations

import enum
from datetime import UTC
from datetime import datetime
from uuid import UUID
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as SAUUID
from sqlmodel import Field
from sqlmodel import SQLModel

from app.infrastructure.models.auth_user_model import AuthUserModel  # noqa: F401


# ==================================================================================================
# 지식 소스 유형 정의
# --------------------------------------------------------------------------------------------------
# 지식 베이스에 등록되는 소스의 물리적 형태를 정의하는 열거형
# ==================================================================================================
class SourceType(enum.StrEnum):
  FILE = "FILE"
  WEB_URL = "WEB_URL"
  TEXT_SNIPPET = "TEXT_SNIPPET"


# ==================================================================================================
# 지식 처리 상태 정의
# --------------------------------------------------------------------------------------------------
# 지식 데이터의 비동기 처리 단계를 정의하는 열거형
# ==================================================================================================
class ProcessingStatus(enum.StrEnum):
  PENDING = "PENDING"
  ING = "ING"
  DONE = "DONE"
  ERROR = "ERROR"


# ==================================================================================================
# 지식 컬렉션 모델
# --------------------------------------------------------------------------------------------------
# RAG 시스템에서 논리적 문서 묶음인 지식 컬렉션을 정의하는 데이터베이스 모델
# ==================================================================================================
class KnowledgesModel(SQLModel, table=True):
  __tablename__: str = "knowledges"  # pyright: ignore[reportAssignmentType, reportIncompatibleVariableOverride]

  __table_args__ = (
    Index(
      "ix_knowledges_title_desc_pgroonga",
      "title",
      "description",
      postgresql_using="pgroonga",
    ),
    Index(
      "ix_knowledges_owner_deleted",
      "user_id",
      postgresql_where=text("deleted_at IS NULL"),
    ),
  )

  id: UUID = Field(
    default_factory=uuid4,
    sa_column=Column(
      SAUUID(as_uuid=True),
      primary_key=True,
      server_default=text("uuid_generate_v4()"),
    ),
    description="고유 ID",
  )

  user_id: str = Field(
    sa_column=Column(
      SAUUID(as_uuid=False),
      ForeignKey("auth.users.id", ondelete="CASCADE"),
      nullable=False,
      index=True,
    ),
    description="소유자 Supabase Auth UUID(auth.users.id)",
  )

  title: str = Field(
    sa_column=Column(String(255), nullable=False),
    description="지식 저장소 제목",
  )
  description: str = Field(
    default="",
    sa_column=Column(Text, nullable=False, server_default=text("''")),
    description="지식 저장소 상세 설명",
  )
  is_rag_enabled: bool = Field(
    default=True,
    sa_column=Column(Boolean, nullable=False, server_default=text("true")),
    description="RAG 검색 대상 포함 여부",
  )

  created_at: datetime = Field(
    default_factory=lambda: datetime.now(UTC),
    sa_column=Column(
      DateTime(timezone=True),
      nullable=False,
      server_default=text("timezone('utc', now())"),
    ),
  )
  updated_at: datetime = Field(
    default_factory=lambda: datetime.now(UTC),
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


# ==================================================================================================
# 지식 소스 상세 모델
# --------------------------------------------------------------------------------------------------
# 개별 지식 리소스의 상세 정보와 처리 상태를 관리하는 데이터베이스 모델
# ==================================================================================================
class KnowledgeSourcesModel(SQLModel, table=True):
  __tablename__: str = "knowledge_sources"  # pyright: ignore[reportAssignmentType, reportIncompatibleVariableOverride]

  __table_args__ = (
    Index(
      "ix_knowledge_sources_knowledge_id",
      "knowledge_id",
      postgresql_where=text("deleted_at IS NULL"),
    ),
    Index(
      "ix_knowledge_sources_user_id",
      "user_id",
      postgresql_where=text("deleted_at IS NULL"),
    ),
  )

  id: UUID = Field(
    default_factory=uuid4,
    sa_column=Column(
      SAUUID(as_uuid=True),
      primary_key=True,
      server_default=text("uuid_generate_v4()"),
    ),
    description="고유 ID",
  )

  knowledge_id: UUID = Field(
    sa_column=Column(
      SAUUID(as_uuid=True),
      ForeignKey("knowledges.id", ondelete="CASCADE"),
      nullable=False,
    ),
    description="상위 컬렉션 ID",
  )

  user_id: str = Field(
    sa_column=Column(
      SAUUID(as_uuid=False),
      ForeignKey("auth.users.id", ondelete="CASCADE"),
      nullable=False,
    ),
    description="소유자 UUID (RLS 최적화 반정규화)",
  )

  source_type: SourceType = Field(
    default=SourceType.FILE,
    sa_column=Column(SAEnum(SourceType), nullable=False),
    description="소스 형태: FILE, WEB_URL 등",
  )
  display_name: str = Field(
    sa_column=Column(String(255), nullable=False),
    description="화면 노출용 파일/URL 이름",
  )
  storage_path: str = Field(
    default="",
    sa_column=Column(Text, nullable=False, server_default=text("''")),
    description="S3 등 스토리지 객체 상대 경로",
  )
  file_size: int = Field(
    default=0,
    sa_column=Column(Integer, nullable=False, server_default=text("0")),
    description="용량(Bytes)",
  )
  token_count: int = Field(
    default=0,
    sa_column=Column(Integer, nullable=False, server_default=text("0")),
    description="추출/임베딩에 사용된 총 토큰 수량",
  )
  mime_type: str = Field(
    default="application/octet-stream",
    sa_column=Column(String(255), nullable=False, server_default=text("'application/octet-stream'")),
    description="MIME 형식",
  )
  is_rag_enabled: bool = Field(
    default=True,
    sa_column=Column(Boolean, nullable=False, server_default=text("true")),
    description="RAG 검색 대상 포함 여부",
  )

  error_message: str | None = Field(
    default=None,
    sa_column=Column(Text, nullable=True),
    description="파싱 또는 임베딩 실패 사유 상세내용",
  )
  processing_status: ProcessingStatus = Field(
    default=ProcessingStatus.PENDING,
    sa_column=Column(
      SAEnum(ProcessingStatus),
      nullable=False,
      server_default=text("'PENDING'"),
    ),
    description="RAG 후처리 상태",
  )
  processing_error_message: str | None = Field(
    default=None,
    sa_column=Column(Text, nullable=True),
    description="청킹/임베딩 파이프라인 실패 사유",
  )
  processing_started_at: datetime | None = Field(
    default=None,
    sa_column=Column(DateTime(timezone=True), nullable=True),
    description="RAG 후처리 시작 시각",
  )
  processing_completed_at: datetime | None = Field(
    default=None,
    sa_column=Column(DateTime(timezone=True), nullable=True),
    description="RAG 후처리 완료 시각",
  )
  source_metadata: dict | None = Field(
    default=None,
    sa_column=Column(JSONB, nullable=True),
    description="문서 대표 메타데이터",
  )

  created_at: datetime = Field(
    default_factory=lambda: datetime.now(UTC),
    sa_column=Column(
      DateTime(timezone=True),
      nullable=False,
      server_default=text("timezone('utc', now())"),
    ),
  )
  updated_at: datetime = Field(
    default_factory=lambda: datetime.now(UTC),
    sa_column=Column(
      DateTime(timezone=True),
      nullable=False,
      server_default=text("timezone('utc', now())"),
    ),
  )
  deleted_at: datetime | None = Field(
    default=None,
    sa_column=Column(DateTime(timezone=True), nullable=True),
    description="소프트 삭제 타임스탬프 (가비지 컬렉터 처리 용이성 확보)",
  )


# ==================================================================================================
# 지식 청크 모델
# --------------------------------------------------------------------------------------------------
# 분할된 텍스트 청크와 해당 임베딩 벡터를 저장하는 데이터베이스 모델
# ==================================================================================================
class KnowledgeChunksModel(SQLModel, table=True):
  __tablename__: str = "knowledge_chunks"  # pyright: ignore[reportAssignmentType, reportIncompatibleVariableOverride]

  __table_args__ = (
    Index(
      "ix_knowledge_chunks_source_id",
      "source_id",
    ),
    # 텍스트 검색을 위한 PGroonga 인덱스 (기존 키워드 검색)
    Index(
      "ix_knowledge_chunks_content_pgroonga",
      "chunk_content",
      postgresql_using="pgroonga",
    ),
    # 벡터 유사도 검색을 위한 pgvector HNSW 인덱스 (Cosine Similarity 전용 ops)
    Index(
      "ix_knowledge_chunks_embedding_hnsw",
      "embedding",
      postgresql_using="hnsw",
      postgresql_with={"m": 16, "ef_construction": 64},
      postgresql_ops={"embedding": "vector_cosine_ops"},
    ),
  )

  id: UUID = Field(
    default_factory=uuid4,
    sa_column=Column(
      SAUUID(as_uuid=True),
      primary_key=True,
      server_default=text("uuid_generate_v4()"),
    ),
    description="고유 ID",
  )

  source_id: UUID = Field(
    sa_column=Column(
      SAUUID(as_uuid=True),
      ForeignKey("knowledge_sources.id", ondelete="CASCADE"),
      nullable=False,
    ),
    description="부모 소스 ID",
  )

  user_id: str = Field(
    sa_column=Column(
      SAUUID(as_uuid=False),
      ForeignKey("auth.users.id", ondelete="CASCADE"),
      nullable=False,
    ),
    description="소유자 UUID (RLS 필터링 성능 최적화용)",
  )

  chunk_index: int = Field(
    sa_column=Column(Integer, nullable=False),
    description="원본 문서에서의 청크 순번",
  )

  chunk_content: str = Field(
    sa_column=Column(Text, nullable=False),
    description="추출된 텍스트 본문 (전문 검색 대상)",
  )

  # 기본 임베딩 차원을 1536(OpenAI text-embedding-3-small/ada-002 기준)으로 세팅
  embedding: list[float] = Field(
    sa_column=Column(Vector(1536), nullable=False),
    description="pgvector 1536차원 임베딩",
  )

  chunk_metadata: dict | list | None = Field(
    default=None,
    sa_column=Column(JSONB, nullable=True),
    description="해당 청크의 부가 정보 (페이지 번호, 제목 등 JSON 구조화)",
  )

  created_at: datetime = Field(
    default_factory=lambda: datetime.now(UTC),
    sa_column=Column(
      DateTime(timezone=True),
      nullable=False,
      server_default=text("timezone('utc', now())"),
    ),
  )
