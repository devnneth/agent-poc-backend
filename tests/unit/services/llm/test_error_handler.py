from unittest.mock import MagicMock

import httpx
import pytest

from app.infrastructure.common.exceptions import LLMAuthenticationError
from app.infrastructure.common.exceptions import LLMContextWindowError
from app.infrastructure.common.exceptions import LLMError
from app.infrastructure.common.exceptions import LLMQuotaError
from app.infrastructure.common.exceptions import LLMRateLimitError
from app.infrastructure.common.exceptions import LLMServerError
from app.infrastructure.llm.helpers.error_handler import handle_llm_http_error


@pytest.mark.asyncio
async def test_handle_auth_error():
  """401 에러가 LLMAuthenticationError로 변환되는지 테스트합니다."""
  response = MagicMock(spec=httpx.Response)
  response.status_code = 401
  # aread()는 바이트를 반환해야 함
  response.aread.return_value = b'{"error": {"message": "Invalid API Key"}}'

  error = httpx.HTTPStatusError("Auth Error", request=MagicMock(), response=response)

  with pytest.raises(LLMAuthenticationError) as excinfo:
    await handle_llm_http_error(error)

  assert excinfo.value.status_code == 401
  assert "Invalid API Key" in excinfo.value.message


@pytest.mark.asyncio
async def test_handle_context_window_error():
  """컨텍스트 초과 에러가 LLMContextWindowError로 변환되는지 테스트합니다."""
  response = MagicMock(spec=httpx.Response)
  response.status_code = 400
  response.aread.return_value = b'{"error": {"message": "This model\'s maximum context length is 8192 tokens"}}'

  error = httpx.HTTPStatusError("Context Error", request=MagicMock(), response=response)

  with pytest.raises(LLMContextWindowError):
    await handle_llm_http_error(error)


@pytest.mark.asyncio
async def test_handle_rate_limit_error():
  """429 에러가 LLMRateLimitError로 변환되는지 테스트합니다."""
  response = MagicMock(spec=httpx.Response)
  response.status_code = 429
  response.aread.return_value = b'{"message": "Rate limit reached"}'

  error = httpx.HTTPStatusError("Rate Error", request=MagicMock(), response=response)

  with pytest.raises(LLMRateLimitError):
    await handle_llm_http_error(error)


@pytest.mark.asyncio
async def test_handle_quota_error():
  """429 에러 중 쿼터 부족 패턴이 LLMQuotaError로 변환되는지 테스트합니다."""
  quota_messages = [
    '{"error": {"code": "insufficient_quota", "message": "You exceeded your current quota"}}',
    '{"error": {"message": "Your credit balance is too low"}}',
    '{"error": {"message": "billing_limit_reached"}}',
  ]

  for msg in quota_messages:
    response = MagicMock(spec=httpx.Response)
    response.status_code = 429
    response.aread.return_value = msg.encode("utf-8")

    error = httpx.HTTPStatusError("Quota Error", request=MagicMock(), response=response)

    with pytest.raises(LLMQuotaError):
      await handle_llm_http_error(error)


@pytest.mark.asyncio
async def test_handle_server_error():
  """500 에러가 LLMServerError로 변환되는지 테스트합니다."""
  response = MagicMock(spec=httpx.Response)
  response.status_code = 500
  response.aread.return_value = b"Internal Server Error"

  error = httpx.HTTPStatusError("Server Error", request=MagicMock(), response=response)

  with pytest.raises(LLMServerError):
    await handle_llm_http_error(error)


@pytest.mark.asyncio
async def test_handle_generic_llm_error():
  """기타 상태 코드가 LLMError로 변환되는지 테스트합니다."""
  response = MagicMock(spec=httpx.Response)
  response.status_code = 418  # I'm a teapot
  response.aread.return_value = b"Teapot Error"

  error = httpx.HTTPStatusError("Teapot", request=MagicMock(), response=response)

  with pytest.raises(LLMError) as excinfo:
    await handle_llm_http_error(error)
  assert excinfo.value.status_code == 418
