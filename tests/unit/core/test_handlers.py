from unittest.mock import MagicMock

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError

from app.api.common.exception_handlers import http_exception_handler
from app.api.common.exception_handlers import llm_error_handler
from app.api.common.exception_handlers import validation_exception_handler
from app.infrastructure.common.exceptions import LLMContextWindowError
from app.infrastructure.common.exceptions import LLMError


def test_http_exception_handler():
  """HTTPException 발생 시 공통 응답 포맷으로 변환되는지 테스트합니다."""
  request = MagicMock()
  exc = HTTPException(status_code=403, detail="Forbidden Action")

  response = http_exception_handler(request, exc)
  data = bytes(response.body).decode("utf-8")
  import json

  data_json = json.loads(data)

  assert response.status_code == 403
  assert data_json["error"] is True
  assert data_json["message"] == "Forbidden Action"
  assert data_json["status"] == 403


def test_validation_exception_handler():
  """유효성 검사 에러 발생 시 공통 응답 포맷으로 변환되는지 테스트합니다."""
  request = MagicMock()
  exc = RequestValidationError(
    errors=[{"loc": ["body", "email"], "msg": "invalid email", "type": "value_error"}],
  )

  response = validation_exception_handler(request, exc)
  assert response.status_code == 422

  import json

  data_json = json.loads(bytes(response.body).decode("utf-8"))
  assert data_json["code"] == "VALIDATION_ERROR"
  assert "body" in str(data_json["detail"])


def test_llm_error_handler():
  """LLMError 발생 시 공통 응답 포맷으로 변환되는지 테스트합니다."""
  request = MagicMock()
  exc = LLMError(message="API Quota Exceeded", status_code=429, response_body='{"error": "limit"}')

  response = llm_error_handler(request, exc)
  assert response.status_code == 429

  import json

  data_json = json.loads(bytes(response.body).decode("utf-8"))
  assert data_json["code"] == "LLM_ERROR"
  assert data_json["detail"] == '{"error": "limit"}'


def test_llm_context_window_error_handler():
  """LLMContextWindowError 발생 시 전용 에러 코드가 포함되는지 테스트합니다."""
  request = MagicMock()
  exc = LLMContextWindowError(message="Too long", status_code=400)

  response = llm_error_handler(request, exc)
  import json

  data_json = json.loads(bytes(response.body).decode("utf-8"))

  assert data_json["code"] == "LLM_CONTEXT_EXCEEDED"
