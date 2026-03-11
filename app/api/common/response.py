from typing import Any

from app.api.common.response_entity import CommonResponse


def ok(result: Any, status: int = 200, message: str = "") -> CommonResponse:
  if result is None:
    result = True
  return CommonResponse(result=result, message=message, error=False, status=status)


def fail(
  message: str,
  status: int,
  result: Any | None = None,
  code: str | None = None,
  detail: Any | None = None,
) -> CommonResponse:
  return CommonResponse(
    result=result,
    message=message,
    error=True,
    status=status,
    code=code,
    detail=detail,
  )
