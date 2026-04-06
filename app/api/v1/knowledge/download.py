from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.api.common.jwt_request import jwt_required
from app.features.knowledge.knowledge_file_service import KnowledgeService
from app.infrastructure.persistence.database import get_session

router = APIRouter()


# ==================================================================================================
# 지식 소스 다운로드
# --------------------------------------------------------------------------------------------------
# 지정된 지식 소스 파일을 시스템에서 내려받음
# ==================================================================================================
@router.get("/{knowledge_id}/sources/{source_id}/download")
async def download_knowledge_source(
  knowledge_id: UUID,
  source_id: UUID,
  session: Session = Depends(get_session),
  claims: dict = Depends(jwt_required),
):
  user_id = str(claims.get("sub", ""))
  if not user_id:
    raise HTTPException(status_code=401, detail="사용자 인증 정보가 부족합니다.")

  source, file_path = KnowledgeService.get_downloadable_knowledge_source(
    session=session,
    knowledge_id=knowledge_id,
    source_id=source_id,
    user_id=user_id,
  )
  return FileResponse(
    path=file_path,
    media_type=source.mime_type,
    filename=source.display_name,
  )
