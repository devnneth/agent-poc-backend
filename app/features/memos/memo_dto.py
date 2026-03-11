from datetime import UTC
from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from app.infrastructure.models.memo_model import MemoModel


class MemoCreate(BaseModel):
  """메모(Memo) 생성용 DTO입니다."""

  title: str = Field(default="제목 없는 메모", description="메모 제목")
  content: str = Field(default="", description="메모 본문")

  def to_model(self, owner_user_id: str) -> MemoModel:
    now = datetime.now(UTC)
    return MemoModel(
      owner_user_id=owner_user_id,
      title=self.title,
      content=self.content,
      created_at=now,
      updated_at=now,
    )


class MemoUpdate(BaseModel):
  """메모(Memo) 수정용 DTO입니다."""

  title: str | None = None
  content: str | None = None


class MemoSearchFilter(BaseModel):
  """하이브리드 조회를 위한 필터 DTO입니다."""

  keyword: str | None = Field(default=None, description="검색할 키워드 (Hybrid 검색용)")
  query_vector: list[float] | None = Field(default=None, description="키워드의 임베딩 벡터 (Hybrid 검색용)")
