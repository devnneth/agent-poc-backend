from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import status

from app.api.common.response import ok
from app.api.common.response_entity import CommonResponse
from app.features.auth.auth_entity import AuthRefreshRequest
from app.features.auth.auth_service import AuthService

router = APIRouter()


@router.post("/refresh", response_model=CommonResponse)
async def refresh(payload: AuthRefreshRequest) -> CommonResponse:
  try:
    result = AuthService.get_instance().refresh_session(
      payload.refresh_token,
      payload.google_refresh_token,
    )
    return ok(result)
  except Exception as exc:
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="토큰 갱신 처리 중 오류가 발생했습니다.",
    ) from exc
