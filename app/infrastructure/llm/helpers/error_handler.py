import json
import logging
from typing import NoReturn

import httpx

from app.infrastructure.common.exceptions import LLMAuthenticationError
from app.infrastructure.common.exceptions import LLMContextWindowError
from app.infrastructure.common.exceptions import LLMError
from app.infrastructure.common.exceptions import LLMInvalidRequestError
from app.infrastructure.common.exceptions import LLMQuotaError
from app.infrastructure.common.exceptions import LLMRateLimitError
from app.infrastructure.common.exceptions import LLMServerError


async def handle_llm_http_error(e: httpx.HTTPStatusError) -> NoReturn:
  """httpx.HTTPStatusError를 분석하여 적절한 LLMError 계열 예외를 발생시킵니다."""
  status_code = e.response.status_code

  try:
    response_body = await e.response.aread()
    response_text = response_body.decode("utf-8")
  except Exception:
    response_text = "응답 본문을 읽을 수 없습니다."

  message = response_text
  try:
    data = json.loads(response_text)
    if "error" in data:
      error_data = data["error"]
      message = error_data.get("message", response_text) if isinstance(error_data, dict) else str(error_data)
    elif "message" in data:
      message = data["message"]
  except Exception:
    logging.exception("Failed to parse error response body")

  context_patterns = [
    "maximum context length",
    "max_tokens",
    "max_completion_tokens",
    "too large",
    "length limit",
    "context window",
  ]

  is_context_error = any(pattern in message.lower() for pattern in context_patterns)

  quota_patterns = [
    "insufficient_quota",
    "exceeded your current quota",
    "billing_not_active",
    "billing_limit_reached",
    "balance",
    "credit",
  ]

  is_quota_error = any(pattern in message.lower() for pattern in quota_patterns)

  if status_code == 401:
    raise LLMAuthenticationError(message, status_code, response_text)
  if status_code == 400:
    if is_context_error:
      raise LLMContextWindowError(message, status_code, response_text)
    raise LLMInvalidRequestError(message, status_code, response_text)
  if status_code == 429:
    if is_quota_error:
      raise LLMQuotaError(message, status_code, response_text)
    raise LLMRateLimitError(message, status_code, response_text)
  if status_code >= 500:
    raise LLMServerError(message, status_code, response_text)
  raise LLMError(message, status_code, response_text)
