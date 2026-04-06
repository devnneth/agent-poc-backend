from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import File
from fastapi import HTTPException
from fastapi import UploadFile
from sqlmodel import Session

from app.api.common.jwt_request import jwt_required
from app.features.knowledge.knowledge_file_service import KnowledgeService
from app.infrastructure.persistence.database import get_session

router = APIRouter()


# ==================================================================================================
# 지식 파일 업로드
# --------------------------------------------------------------------------------------------------
# 지식 저장소에 파일을 업로드하고 확장자 검증 및 메타데이터를 저장
# ==================================================================================================
@router.post("/{knowledge_id}/upload")
async def upload_knowledge_file(
  knowledge_id: UUID,
  file: UploadFile = File(...),
  session: Session = Depends(get_session),
  claims: dict = Depends(jwt_required),
):
  user_id = str(claims.get("sub", ""))
  if not user_id:
    raise HTTPException(status_code=401, detail="사용자 인증 정보가 부족합니다.")

  return KnowledgeService.upload_knowledge_file(
    session=session,
    knowledge_id=knowledge_id,
    user_id=user_id,
    file=file,
  )
