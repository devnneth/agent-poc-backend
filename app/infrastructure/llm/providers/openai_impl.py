from typing import Any

from app.infrastructure.llm.providers.openai_compatible_impl import OpenAICompatibleImpl


class OpenAIImpl(OpenAICompatibleImpl):
  """OpenAI 스트리밍 응답을 전담 구현하는 클래스 (Infrastructure Layer)"""

  def __init__(self, api_key: str | None = None, base_url: str | None = None):
    """OpenAI 호출에 사용할 인증키와 base URL을 관리합니다."""
    super().__init__(
      provider_label="OpenAI",
      api_key_name="OPENAI_API_KEY",
      base_url_name="OPENAI_BASE_URL",
      api_key=api_key,
      base_url=base_url or "https://api.openai.com",
      require_base_url=False,
    )

  async def rerank(self, query: str, documents: list[str], **kwargs: Any) -> list[dict[str, Any]]:
    return await super().rerank(query, documents, **kwargs)
