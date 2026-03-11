from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import status

from app.api.common.response import ok
from app.api.common.response_entity import CommonResponse
from app.features.auth.auth_entity import AuthLoginRequest
from app.features.auth.auth_service import AuthService

router = APIRouter()


@router.post("/login", response_model=CommonResponse)
async def login(payload: AuthLoginRequest) -> CommonResponse:
  try:
    result = AuthService.get_instance().login(
      email=payload.email,
      password=payload.password,
    )
    return ok(result)
  except Exception as exc:
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="로그인 처리 중 오류가 발생했습니다.",
    ) from exc
