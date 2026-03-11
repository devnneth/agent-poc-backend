from collections.abc import AsyncIterator
from typing import Any
from typing import Protocol


class LLMProviderInterface(Protocol):
  """LLM 스트리밍 클라이언트 공통 인터페이스입니다. (Infrastructure Layer)"""

  def stream_chat(
    self,
    prompt: str | None = None,
    *,
    messages: list[dict[str, str]] | None = None,
    **kwargs: Any,
  ) -> AsyncIterator[str]:
    """프롬프트 또는 메시지 히스토리에 대한 스트리밍 텍스트 청크를 반환합니다."""
    ...

  async def embed(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
    """텍스트 목록에 대한 임베딩 벡터 목록을 반환합니다."""
    ...

  async def rerank(self, query: str, documents: list[str], **kwargs: Any) -> list[dict[str, Any]]:
    """쿼리와 문서 목록을 재정렬한 결과를 반환합니다."""
    ...

  def get_langchain_model(self, model_name: str, temperature: float = 0.0, streaming: bool = True, **kwargs: Any) -> Any:
    """LangChain용 BaseChatModel 인스턴스를 반환합니다."""
    ...
