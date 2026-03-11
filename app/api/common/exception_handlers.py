from typing import cast

from fastapi import HTTPException
from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.common.response import fail
from app.infrastructure.common.exceptions import LLMAuthenticationError
from app.infrastructure.common.exceptions import LLMContextWindowError
from app.infrastructure.common.exceptions import LLMError
from app.infrastructure.common.exceptions import LLMInvalidRequestError
from app.infrastructure.common.exceptions import LLMQuotaError
from app.infrastructure.common.exceptions import LLMRateLimitError
from app.infrastructure.common.exceptions import LLMServerError


def http_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
  http_exc = cast(HTTPException, exc)
  detail = http_exc.detail

  if isinstance(detail, dict):
    message = detail.get("message", str(detail))
    error_code = detail.get("code")
    error_detail = detail.get("detail")
  else:
    message = str(detail)
    error_code = "HTTP_ERROR"
    error_detail = None

  payload = fail(
    message=message,
    status=http_exc.status_code,
    code=error_code,
    detail=error_detail,
  ).model_dump()
  return JSONResponse(status_code=http_exc.status_code, content=payload)


def validation_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
  val_exc = cast(RequestValidationError, exc)
  payload = fail(
    message="요청 값이 올바르지 않습니다.",
    status=422,
    code="VALIDATION_ERROR",
    detail=jsonable_encoder(val_exc.errors()),
  ).model_dump()
  return JSONResponse(status_code=422, content=payload)


def unhandled_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
  payload = fail(
    message="서버 오류가 발생했습니다.",
    status=500,
    code="INTERNAL_SERVER_ERROR",
  ).model_dump()
  return JSONResponse(status_code=500, content=payload)


def get_llm_error_info(exc: LLMError) -> tuple[str, str]:
  """LLM 예외로부터 사용자 친화적인 메시지와 에러 코드를 반환합니다."""
  mapping = {
    LLMQuotaError: ("LLM 서비스 쿼터(잔액)가 부족합니다. 서비스 설정 및 결제 정보를 확인해주세요.", "LLM_QUOTA_EXCEEDED"),
    LLMRateLimitError: ("요청 한도가 초과되었습니다. 잠시 후 다시 시도해주세요.", "LLM_RATE_LIMIT_EXCEEDED"),
    LLMAuthenticationError: ("LLM 인증에 실패했습니다. API 키 설정을 확인해주세요.", "LLM_AUTHENTICATION_ERROR"),
    LLMContextWindowError: ("입력 내용이 너무 깁니다. 내용을 줄여서 다시 시도해주세요.", "LLM_CONTEXT_EXCEEDED"),
    LLMServerError: ("LLM 서비스에 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요.", "LLM_SERVER_ERROR"),
    LLMInvalidRequestError: ("잘못된 요청입니다. 요청 내용을 확인해주세요.", "LLM_INVALID_REQUEST"),
  }

  for exc_class, (message, code) in mapping.items():
    if isinstance(exc, exc_class):
      return message, code

  return str(exc) or "LLM 서비스 이용 중 오류가 발생했습니다.", "LLM_ERROR"


def llm_error_handler(_request: Request, exc: LLMError) -> JSONResponse:
  """LLM 서비스에서 발생하는 예외를 공통 포맷으로 변환합니다."""
  status_code = exc.status_code or 400
  message, code = get_llm_error_info(exc)

  payload = fail(
    message=message,
    status=status_code,
    code=code,
    detail=exc.response_body,
  ).model_dump()

  return JSONResponse(status_code=status_code, content=payload)
