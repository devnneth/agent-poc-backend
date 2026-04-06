from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from pydantic import Field

KnowledgeSearchMode = Literal["sparse", "dense", "hybrid"]


# ==================================================================================================
# 지식 검색 입력 스키마
# --------------------------------------------------------------------------------------------------
# 지식 RAG 도구에서 사용하는 입력 데이터 구조를 정의합니다
# ==================================================================================================
class KnowledgeSearchInput(BaseModel):
  query: str = Field(min_length=1, description="검색할 질의문")
  sparse_query: str | None = Field(default=None, min_length=1, description="희소검색용 질의문. 보통 사용자의 원문 표현을 유지합니다.")
  dense_query: str | None = Field(default=None, min_length=1, description="밀집검색용 질의문. 필요하면 의미 중심으로 재작성합니다.")
  top_k: int = Field(default=5, ge=1, le=20, description="반환할 최대 청크 수")


# ==================================================================================================
# 지식 검색 결과 항목
# --------------------------------------------------------------------------------------------------
# 검색 결과의 개별 청크 단위 데이터 항목을 정의합니다
# ==================================================================================================
class KnowledgeSearchResultItem(BaseModel):
  chunk_id: UUID
  source_id: UUID
  display_name: str
  chunk_index: int
  content: str
  score: float
  chunk_metadata: dict | list | None = None


# ==================================================================================================
# 지식 검색 결과 응답
# --------------------------------------------------------------------------------------------------
# 검색 결과의 전체 응답 구조를 정의합니다
# ==================================================================================================
class KnowledgeSearchResult(BaseModel):
  knowledge_id: UUID
  knowledge_title: str
  search_mode: KnowledgeSearchMode
  results: list[KnowledgeSearchResultItem]
