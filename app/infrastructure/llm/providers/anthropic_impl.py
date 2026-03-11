import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from langchain_anthropic import ChatAnthropic
from pydantic import SecretStr

from app.infrastructure.llm.helpers.http_client import stream_llm_request
from app.infrastructure.llm.providers.llm_provider_interface import LLMProviderInterface


class AnthropicImpl(LLMProviderInterface):
  """Anthropic 스트리밍 응답을 전담 구현하는 클래스 (Infrastructure Layer)"""

  def __init__(self, api_key: str | None = None):
    self._api_key = api_key
    self._base_url = "https://api.anthropic.com"
    self._logger = logging.getLogger(__name__)

  async def stream_chat(
    self,
    prompt: str | None = None,
    *,
    messages: list[dict[str, str]] | None = None,
    **kwargs: Any,
  ) -> AsyncIterator[str]:
    if not self._api_key:
      raise ValueError("ANTHROPIC_API_KEY가 설정되지 않았습니다.")
    model = kwargs.get("model")
    if not model:
      raise ValueError("Anthropic 요청에는 model 값이 필요합니다.")
    max_tokens = kwargs.get("max_tokens")
    if not max_tokens:
      raise ValueError("Anthropic 요청에는 max_tokens 값이 필요합니다.")

    # workflow 제거 이후 기본 시스템 프롬프트를 사용합니다.
    system_prompt = "You are a helpful assistant."

    if messages:
      chat_messages = [m for m in messages if m.get("role") != "system"]
    elif prompt:
      chat_messages = [{"role": "user", "content": prompt}]
    else:
      raise ValueError("prompt 또는 messages 중 하나는 필수입니다")

    payload: dict[str, Any] = {
      "model": model,
      "max_tokens": max_tokens,
      "messages": chat_messages,
      "system": system_prompt,
      "stream": True,
    }
    temperature = kwargs.get("temperature")
    if temperature is not None:
      payload["temperature"] = temperature

    url = f"{self._base_url}/v1/messages"
    headers = {
      "x-api-key": self._api_key,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json",
    }
    async with stream_llm_request(url, payload, headers) as response:
      async for line in response.aiter_lines():
        if not line or not line.startswith("data:"):
          continue
        data = line.replace("data:", "", 1).strip()
        if not data:
          continue
        text, is_done = self._extract_delta_text(data)
        if text:
          yield f"data: {text}\n\n"
        if is_done:
          yield "data: [DONE]\n\n"
          break

  async def embed(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
    raise NotImplementedError("Anthropic 제공자는 embedding을 지원하지 않습니다")

  async def rerank(self, query: str, documents: list[str], **kwargs: Any) -> list[dict[str, Any]]:
    raise NotImplementedError("Anthropic 제공자는 rerank를 지원하지 않습니다")

  def get_langchain_model(
    self,
    model_name: str,
    temperature: float = 0.0,
    streaming: bool = True,
    **kwargs: Any,
  ) -> ChatAnthropic:
    """Anthropic LangChain 채팅 모델을 반환합니다."""
    return ChatAnthropic(
      model_name=model_name,
      api_key=SecretStr(self._api_key or ""),
      temperature=temperature,
      streaming=streaming,
      **kwargs,
    )

  def _extract_delta_text(self, data: str) -> tuple[str, bool]:
    try:
      parsed = json.loads(data)
    except json.JSONDecodeError:
      return "", False
    event_type = parsed.get("type")
    if event_type == "content_block_delta":
      delta = parsed.get("delta") or {}
      if delta.get("type") == "text_delta":
        return delta.get("text") or "", False
      return "", False
    if event_type == "message_stop":
      return "", True
    if event_type == "error":
      error = parsed.get("error") or {}
      message = error.get("message") or "Anthropic error"
      raise ValueError(message)
    return "", False
