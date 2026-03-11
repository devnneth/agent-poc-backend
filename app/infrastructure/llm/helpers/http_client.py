import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx

from app.infrastructure.llm.helpers.error_handler import handle_llm_http_error

logger = logging.getLogger(__name__)


@asynccontextmanager
async def stream_llm_request(
  url: str,
  payload: dict[str, Any],
  headers: dict[str, str],
  timeout: float = 60.0,
) -> AsyncIterator[httpx.Response]:
  """LLM 제공자에게 스트리밍 요청을 보내는 공통 컨텍스트 매니저입니다."""
  client_timeout = httpx.Timeout(timeout, read=None)
  try:
    async with (
      httpx.AsyncClient(timeout=client_timeout) as client,
      client.stream("POST", url, json=payload, headers=headers) as response,
    ):
      if response.status_code >= 400:
        await response.aread()
      response.raise_for_status()
      yield response
  except httpx.HTTPStatusError as e:
    await handle_llm_http_error(e)
  except Exception:
    logger.exception("LLM 스트리밍 요청 중 예외 발생: %s", url)
    raise


async def post_llm_request(
  url: str,
  payload: dict[str, Any],
  headers: dict[str, str],
  timeout: float = 60.0,
) -> dict[str, Any]:
  """LLM 제공자에게 일반 POST 요청을 보내고 JSON 응답을 반환하는 공통 함수입니다."""
  client_timeout = httpx.Timeout(timeout)
  try:
    async with httpx.AsyncClient(timeout=client_timeout) as client:
      response = await client.post(url, json=payload, headers=headers)
      response.raise_for_status()
      return response.json()
  except httpx.HTTPStatusError as e:
    await handle_llm_http_error(e)
  except Exception:
    logger.exception("LLM POST 요청 중 예외 발생: %s", url)
    raise
