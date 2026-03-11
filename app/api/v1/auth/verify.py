from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Query
from fastapi import status

from app.api.common.response import ok
from app.api.common.response_entity import CommonResponse
from app.features.auth.auth_service import AuthService

router = APIRouter()


@router.post("/verify", response_model=CommonResponse)
async def verify_access_token(
  access_token: str = Query(..., min_length=1, description="인증 토큰"),
) -> CommonResponse:
  try:
    token = access_token.replace("Bearer ", "").strip()
    if not token:
      raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="access_token이 필요합니다.",
      )
    result = AuthService.get_instance().verify_token(token)
    return ok(bool(result.get("valid")))
  except HTTPException:
    raise
  except Exception as exc:
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="토큰 검증 처리 중 오류가 발생했습니다.",
    ) from exc
