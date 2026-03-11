from typing import Any

from app.infrastructure.llm.helpers.http_client import post_llm_request
from app.infrastructure.llm.providers.openai_compatible_impl import OpenAICompatibleImpl


class CustomImpl(OpenAICompatibleImpl):
  """OpenAI 호환 커스텀 LLM 스트리밍 응답을 전담 구현하는 클래스 (Infrastructure Layer)"""

  def __init__(
    self,
    base_url: str | None = None,
    api_key: str | None = None,
    chat_url: str | None = None,
    embeddings_url: str | None = None,
    rerank_url: str | None = None,
  ):
    super().__init__(
      provider_label="Custom",
      api_key_name="CUSTOM_API_KEY",
      base_url_name="CUSTOM_BASE_URL",
      api_key=api_key,
      base_url=base_url,
      require_base_url=True,
    )
    self._chat_url = chat_url or "/v1/chat/completions"
    self._embeddings_url = embeddings_url or "/v1/embeddings"
    self._rerank_url = rerank_url or "/v1/rerank"

  def _build_chat_url(self) -> str:
    return self._build_custom_url(self._chat_url)

  def _build_embeddings_url(self) -> str:
    return self._build_custom_url(self._embeddings_url)

  def _build_rerank_url(self) -> str:
    return self._build_custom_url(self._rerank_url)

  def _build_custom_url(self, endpoint: str) -> str:
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
      return endpoint
    base = self._base_url.rstrip("/")
    path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    return f"{base}{path}"

  async def rerank(self, query: str, documents: list[str], **kwargs: Any) -> list[dict[str, Any]]:
    if not self._api_key:
      raise ValueError("CUSTOM_API_KEY가 설정되지 않았습니다")
    if not self._base_url:
      raise ValueError("CUSTOM_BASE_URL이 설정되지 않았습니다")
    model = kwargs.get("model")
    if not model:
      raise ValueError("Custom LLM 요청에는 model 값이 필요합니다")

    payload: dict[str, Any] = {
      "model": model,
      "query": query,
      "documents": documents,
    }
    top_n = kwargs.get("top_n")
    if top_n is not None:
      payload["top_n"] = top_n

    url = self._build_rerank_url()
    headers = {
      "Authorization": f"Bearer {self._api_key}",
      "content-type": "application/json",
    }
    data = await post_llm_request(url, payload, headers)
    return self._extract_rerank_results(data, documents)

  def _extract_rerank_results(
    self,
    data: dict[str, Any],
    documents: list[str],
  ) -> list[dict[str, Any]]:
    results = data.get("results") or []
    normalized: list[dict[str, Any]] = []
    for result in results:
      index = result.get("index")
      if index is None:
        index = -1
      score = result.get("relevance_score") or result.get("score") or 0.0
      document = result.get("document")
      text = ""
      if isinstance(document, dict):
        text = document.get("text") or ""
      elif isinstance(document, str):
        text = document
      if text == "" and isinstance(index, int) and 0 <= index < len(documents):
        text = documents[index]
      normalized.append(
        {
          "index": index,
          "score": score,
          "text": text,
        },
      )
    return normalized
