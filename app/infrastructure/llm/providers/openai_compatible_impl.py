import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.infrastructure.common.sse import iter_sse_data
from app.infrastructure.llm.helpers.http_client import post_llm_request
from app.infrastructure.llm.helpers.http_client import stream_llm_request
from app.infrastructure.llm.providers.llm_provider_interface import LLMProviderInterface


class OpenAICompatibleImpl(LLMProviderInterface):
  """OpenAI 호환 스트리밍 공통 로직을 전담 구현하는 베이스 클래스 (Infrastructure Layer)"""

  def __init__(
    self,
    *,
    provider_label: str,
    api_key_name: str,
    base_url_name: str,
    api_key: str | None,
    base_url: str | None,
    require_base_url: bool,
  ):
    """공통 설정과 검증용 메타 정보를 초기화합니다."""
    self._provider_label = provider_label
    self._api_key_name = api_key_name
    self._base_url_name = base_url_name
    self._api_key = api_key
    self._base_url = base_url.rstrip("/") if base_url else ""
    self._require_base_url = require_base_url
    self._logger = logging.getLogger(__name__)

  async def stream_chat(
    self,
    prompt: str | None = None,
    *,
    messages: list[dict[str, str]] | None = None,
    **kwargs: Any,
  ) -> AsyncIterator[str]:
    """OpenAI 호환 채팅 스트리밍 응답을 SSE 형식으로 반환합니다."""
    if not self._api_key:
      raise ValueError(f"{self._api_key_name}가 설정되지 않았습니다")
    if self._require_base_url and not self._base_url:
      raise ValueError(f"{self._base_url_name}가 설정되지 않았습니다")
    model = kwargs.get("model")
    if not model:
      raise ValueError(f"{self._provider_label} 요청에는 model 값이 필요합니다")

    # workflow 제거 이후 기본 시스템 프롬프트를 사용합니다.
    system_prompt = "You are a helpful assistant."

    if messages:
      if messages and messages[0].get("role") == "system":
        chat_messages = [{"role": "system", "content": system_prompt}, *messages[1:]]
      else:
        chat_messages = [{"role": "system", "content": system_prompt}, *messages]
    elif prompt:
      chat_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
      ]
    else:
      raise ValueError("prompt 또는 messages 중 하나는 필수입니다")

    payload: dict[str, Any] = {
      "model": model,
      "messages": chat_messages,
      "stream": True,
    }
    temperature = kwargs.get("temperature")
    if temperature is not None:
      payload["temperature"] = temperature
    max_tokens = kwargs.get("max_tokens")
    if max_tokens is not None:
      payload["max_tokens"] = max_tokens

    url = self._build_chat_url()
    headers = {
      "Authorization": f"Bearer {self._api_key}",
      "content-type": "application/json",
    }
    async with stream_llm_request(url, payload, headers) as response:
      async for data in iter_sse_data(response):
        if data == "[DONE]":
          yield "data: [DONE]\n\n"
          break
        chunk = self._extract_delta_text(data)
        if chunk != "":
          yield f"data: {chunk}\n\n"

  async def embed(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
    """OpenAI 호환 임베딩 API 응답을 공통 포맷으로 반환합니다."""
    if not self._api_key:
      raise ValueError(f"{self._api_key_name}가 설정되지 않았습니다")
    if self._require_base_url and not self._base_url:
      raise ValueError(f"{self._base_url_name}가 설정되지 않았습니다")
    model = kwargs.get("model")
    if not model:
      raise ValueError(f"{self._provider_label} 요청에는 model 값이 필요합니다")

    payload: dict[str, Any] = {
      "model": model,
      "input": texts,
    }
    dimensions = kwargs.get("dimensions")
    if dimensions is not None:
      payload["dimensions"] = dimensions

    url = self._build_embeddings_url()
    headers = {
      "Authorization": f"Bearer {self._api_key}",
      "content-type": "application/json",
    }
    data = await post_llm_request(url, payload, headers)
    return self._extract_embeddings(data)

  async def rerank(self, query: str, documents: list[str], **kwargs: Any) -> list[dict[str, Any]]:
    raise NotImplementedError(f"{self._provider_label} 제공자는 rerank를 지원하지 않습니다")

  def get_langchain_model(
    self,
    model_name: str,
    temperature: float = 0.0,
    streaming: bool = True,
    **kwargs: Any,
  ) -> ChatOpenAI:
    """OpenAI 호환 LangChain 채팅 모델을 반환합니다."""
    base_url = self._base_url
    if base_url and not base_url.endswith("/v1"):
      base_url = f"{base_url}/v1"

    return ChatOpenAI(
      base_url=base_url or None,
      api_key=SecretStr(self._api_key or ""),
      model=model_name,
      temperature=temperature,
      streaming=streaming,
      **kwargs,
    )

  def _build_chat_url(self) -> str:
    if self._base_url.endswith("/v1"):
      return f"{self._base_url}/chat/completions"
    if self._base_url.endswith("/v1/"):
      return f"{self._base_url}chat/completions"
    return f"{self._base_url}/v1/chat/completions"

  def _build_embeddings_url(self) -> str:
    if self._base_url.endswith("/v1"):
      return f"{self._base_url}/embeddings"
    if self._base_url.endswith("/v1/"):
      return f"{self._base_url}embeddings"
    return f"{self._base_url}/v1/embeddings"

  def _extract_delta_text(self, data: str) -> str:
    try:
      parsed = json.loads(data)
    except json.JSONDecodeError:
      return ""
    choices = parsed.get("choices") or []
    if not choices:
      return ""
    delta = choices[0].get("delta") or {}
    content = delta.get("content")
    return content or ""

  def _extract_embeddings(self, data: dict[str, Any]) -> list[list[float]]:
    items = data.get("data") or []
    if not items:
      return []
    has_index = all("index" in item for item in items)
    if has_index:
      items = sorted(items, key=lambda item: item.get("index", 0))
    embeddings: list[list[float]] = []
    for item in items:
      embedding = item.get("embedding")
      if embedding is not None:
        embeddings.append(embedding)
    return embeddings
