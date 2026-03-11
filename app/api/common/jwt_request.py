from datetime import UTC
from datetime import datetime
from typing import Any

from fastapi import Header
from fastapi import HTTPException
from fastapi import Request
from fastapi import status

from app.features.auth.auth_service import AuthService


def _extract_claims_payload(claims: Any) -> dict[str, Any] | None:
  if not isinstance(claims, dict):
    return None
  nested_claims = claims.get("claims")
  if isinstance(nested_claims, dict):
    return nested_claims
  return claims


def _parse_exp_timestamp(exp_value: Any) -> int | None:
  if isinstance(exp_value, (int, float)):
    return int(exp_value)
  if isinstance(exp_value, str) and exp_value.isdigit():
    return int(exp_value)
  return None


def _extract_token(authorization: str | None) -> str | None:
  if not authorization:
    return None
  token = authorization.strip()
  if token.startswith("Bearer "):
    return token.replace("Bearer ", "", 1).strip()
  return token


def jwt_required(
  request: Request,
  authorization: str | None = Header(None),
) -> dict[str, Any]:
  """모든 API 요청에 적용되는 JWT 인증 의존성"""
  token = _extract_token(authorization)
  if not token:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Authorization 헤더가 필요합니다.",
    )

  verification = AuthService.get_instance().verify_token(token)
  if verification.get("valid") is not True:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="유효하지 않은 access_token입니다.",
    )

  claims_payload = _extract_claims_payload(verification.get("claims"))
  if not claims_payload:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="클레임 정보를 확인할 수 없습니다.",
    )

  exp_timestamp = _parse_exp_timestamp(claims_payload.get("exp"))
  if exp_timestamp is None:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="만료 정보를 확인할 수 없습니다.",
    )

  now_timestamp = int(datetime.now(UTC).timestamp())
  if now_timestamp >= exp_timestamp:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="access_token이 만료되었습니다.",
    )

  sub = claims_payload.get("sub")
  if not sub:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="사용자 식별자(sub)를 찾을 수 없습니다.",
    )

  request.state.claims = claims_payload
  return claims_payload
