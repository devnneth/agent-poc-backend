import logging
from typing import Any

from fastapi import APIRouter
from fastapi import Depends
from pydantic import BaseModel
from pydantic import Field

from app.api.common.jwt_request import jwt_required
from app.api.common.response import fail
from app.api.common.response import ok
from app.api.common.response_entity import CommonResponse
from app.infrastructure.persistence.checkpointer import checkpointer

router = APIRouter(prefix="/agent", tags=["agent"])
logger = logging.getLogger(__name__)


class DeleteSessionsRequest(BaseModel):
  """세션 일괄 삭제 요청 DTO"""

  session_ids: list[str] = Field(..., min_length=1, examples=[["session-abc-123", "session-def-456"]])


@router.delete("/session/{session_id}", response_model=CommonResponse)  # swagger용 response 객체타입 지정
async def delete_session(
  session_id: str,
  claims: dict[str, Any] = Depends(jwt_required),
) -> CommonResponse:
  """세션 종료 시 checkpointer에 저장된 해당 세션 데이터를 삭제합니다."""
  user_id: str | None = claims.get("sub")
  try:
    await checkpointer.delete_session(session_id)
    return ok(result={"session_id": session_id, "user_id": user_id})
  except Exception:
    logger.exception(f"세션 삭제 실패: session_id={session_id}, user_id={user_id}")
    return fail(message="세션 삭제 중 오류가 발생했습니다.", status=500)


@router.delete("/sessions", response_model=CommonResponse)  # swagger용 response 객체타입 지정
async def delete_sessions(
  payload: DeleteSessionsRequest,
  claims: dict[str, Any] = Depends(jwt_required),
) -> CommonResponse:
  """여러 세션을 일괄 종료하고 checkpointer 데이터를 병렬로 삭제합니다."""
  user_id: str | None = claims.get("sub")
  try:
    await checkpointer.delete_sessions(payload.session_ids)
    return ok(result={"deleted_session_ids": payload.session_ids, "user_id": user_id})
  except Exception:
    logger.exception(f"세션 일괄 삭제 실패: session_ids={payload.session_ids}, user_id={user_id}")
    return fail(message="세션 일괄 삭제 중 오류가 발생했습니다.", status=500)
