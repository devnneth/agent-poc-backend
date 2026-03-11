import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import SecretStr

from app.infrastructure.common.sse import iter_sse_data
from app.infrastructure.llm.helpers.http_client import post_llm_request
from app.infrastructure.llm.helpers.http_client import stream_llm_request
from app.infrastructure.llm.providers.llm_provider_interface import LLMProviderInterface


class GeminiImpl(LLMProviderInterface):
  """Gemini 스트리밍 응답을 전담 구현하는 클래스 (Infrastructure Layer)"""

  def __init__(self, api_key: str | None = None):
    self._api_key = api_key
    self._base_url = "https://generativelanguage.googleapis.com"
    self._logger = logging.getLogger(__name__)

  async def stream_chat(
    self,
    prompt: str | None = None,
    *,
    messages: list[dict[str, str]] | None = None,
    **kwargs: Any,
  ) -> AsyncIterator[str]:
    if not self._api_key:
      raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다")
    model = kwargs.get("model")
    if not model:
      raise ValueError("Gemini 요청에는 model 값이 필요합니다")

    # workflow 제거 이후 기본 시스템 프롬프트를 사용합니다.
    system_prompt = "You are a helpful assistant."

    if messages:
      contents = []
      for m in messages:
        if m["role"] == "system":
          continue
        role = "user" if m["role"] == "user" else "model"
        contents.append(
          {
            "role": role,
            "parts": [{"text": m["content"]}],
          },
        )
    elif prompt:
      contents = [
        {
          "role": "user",
          "parts": [{"text": prompt}],
        },
      ]
    else:
      raise ValueError("prompt 또는 messages 중 하나는 필수입니다")

    payload: dict[str, Any] = {
      "contents": contents,
      "systemInstruction": {"parts": [{"text": system_prompt}]},
    }
    generation_config: dict[str, Any] = {}
    temperature = kwargs.get("temperature")
    if temperature is not None:
      generation_config["temperature"] = temperature
    max_tokens = kwargs.get("max_tokens")
    if max_tokens is not None:
      generation_config["maxOutputTokens"] = max_tokens
    if generation_config:
      payload["generationConfig"] = generation_config

    url = self._build_stream_url(model)
    headers = {"content-type": "application/json"}
    done_sent = False
    async with stream_llm_request(url, payload, headers) as response:
      async for data in iter_sse_data(response):
        text, is_done = self._extract_delta_text(data)
        if text:
          yield f"data: {text}\n\n"
        if is_done and not done_sent:
          yield "data: [DONE]\n\n"
          done_sent = True
          break

    if not done_sent:
      yield "data: [DONE]\n\n"

  async def embed(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
    if not self._api_key:
      raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다")
    model = kwargs.get("model")
    if not model:
      raise ValueError("Gemini 요청에는 model 값이 필요합니다")
    model_name = self._normalize_model(model)

    requests: list[dict[str, Any]] = []
    dimensions = kwargs.get("dimensions")
    for text in texts:
      request: dict[str, Any] = {
        "model": model_name,
        "content": {
          "parts": [{"text": text}],
        },
      }
      if dimensions is not None:
        request["outputDimensionality"] = dimensions
      requests.append(request)

    payload = {"requests": requests}
    url = f"{self._base_url.rstrip('/')}/v1beta/{model_name}:batchEmbedContents"
    headers = {
      "x-goog-api-key": self._api_key,
      "content-type": "application/json",
    }
    data = await post_llm_request(url, payload, headers)
    if "error" in data:
      message = (data.get("error") or {}).get("message") or "Gemini error"
      raise ValueError(message)
    embeddings = data.get("embeddings") or []
    normalized: list[list[float]] = []
    for embedding in embeddings:
      values = embedding.get("values") or embedding.get("embedding") or embedding.get("vector")
      normalized.append(values or [])
    return normalized

  async def rerank(self, query: str, documents: list[str], **kwargs: Any) -> list[dict[str, Any]]:
    raise NotImplementedError("Gemini 제공자는 rerank를 지원하지 않습니다")

  def get_langchain_model(
    self,
    model_name: str,
    temperature: float = 0.0,
    streaming: bool = True,
    **kwargs: Any,
  ) -> ChatGoogleGenerativeAI:
    """Gemini LangChain 채팅 모델을 반환합니다."""
    return ChatGoogleGenerativeAI(
      model=model_name,
      google_api_key=SecretStr(self._api_key or ""),
      temperature=temperature,
      streaming=streaming,
      **kwargs,
    )

  def _build_stream_url(self, model: str) -> str:
    base = self._base_url.rstrip("/")
    return f"{base}/v1beta/models/{model}:streamGenerateContent?key={self._api_key}"

  def _extract_delta_text(self, data: str) -> tuple[str, bool]:
    try:
      parsed = json.loads(data)
    except json.JSONDecodeError:
      return "", False
    if "error" in parsed:
      message = (parsed.get("error") or {}).get("message") or "Gemini error"
      raise ValueError(message)
    candidates = parsed.get("candidates") or []
    if not candidates:
      return "", False
    candidate = candidates[0] or {}
    content = candidate.get("content") or {}
    parts = content.get("parts") or []
    texts = [part.get("text") or "" for part in parts]
    text = "".join(texts)
    finish_reason = candidate.get("finishReason") or ""
    is_done = bool(finish_reason)
    return text, is_done

  def _normalize_model(self, model: str) -> str:
    if model.startswith("models/"):
      return model
    return f"models/{model}"
