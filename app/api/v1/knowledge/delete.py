from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from sqlmodel import Session

from app.api.common.jwt_request import jwt_required
from app.features.knowledge.knowledge_file_service import KnowledgeService
from app.infrastructure.persistence.database import get_session

router = APIRouter()


# ==================================================================================================
# 지식 소스 삭제
# --------------------------------------------------------------------------------------------------
# 지정된 지식 소스 레코드를 제거하고 연관된 실제 파일까지 삭제
# ==================================================================================================
@router.delete("/{knowledge_id}/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_source(
  knowledge_id: UUID,
  source_id: UUID,
  session: Session = Depends(get_session),
  claims: dict = Depends(jwt_required),
):
  user_id = str(claims.get("sub", ""))
  if not user_id:
    raise HTTPException(status_code=401, detail="사용자 인증 정보가 부족합니다.")

  KnowledgeService.delete_knowledge_source(
    session=session,
    knowledge_id=knowledge_id,
    source_id=source_id,
    user_id=user_id,
  )
