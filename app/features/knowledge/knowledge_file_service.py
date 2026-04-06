import shutil
from datetime import UTC
from datetime import datetime
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException
from fastapi import UploadFile
from fastapi import status
from sqlmodel import Session
from sqlmodel import select

from app.core.config.environment import settings
from app.infrastructure.models.knowledge_model import KnowledgesModel
from app.infrastructure.models.knowledge_model import KnowledgeSourcesModel
from app.infrastructure.models.knowledge_model import ProcessingStatus
from app.infrastructure.models.knowledge_model import SourceType


# ==================================================================================================
# 지식 관리 서비스
# --------------------------------------------------------------------------------------------------
# 문서 업로드, 조회, 삭제 등 지식 베이스 관련 기능을 제공하는 서비스
# ==================================================================================================
class KnowledgeService:
  # ================================================================================================
  # 소유 지식 소스 조회
  # ------------------------------------------------------------------------------------------------
  # 특정 사용자가 소유한 활성화 상태의 지식 소스 정보를 DB에서 조회
  # ================================================================================================
  @staticmethod
  def _get_owned_knowledge_source(
    session: Session,
    knowledge_id: UUID,
    source_id: UUID,
    user_id: str,
  ) -> KnowledgeSourcesModel:
    statement = select(KnowledgeSourcesModel).where(
      KnowledgeSourcesModel.id == source_id,
      KnowledgeSourcesModel.knowledge_id == knowledge_id,
      KnowledgeSourcesModel.user_id == user_id,
      KnowledgeSourcesModel.deleted_at == None,  # noqa: E711
    )
    source = session.exec(statement).first()

    if not source:
      raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="해당 지식 소스를 찾을 수 없거나 권한이 없습니다.",
      )

    return source

  # ================================================================================================
  # 파일 확장자 검증
  # ------------------------------------------------------------------------------------------------
  # 업로드된 파일의 확장자가 시스템에서 허용하는 형식인지 확인
  # ================================================================================================
  @staticmethod
  def validate_file_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in settings.ALLOWED_EXTENSIONS:
      allowed = ", ".join(settings.ALLOWED_EXTENSIONS)
      raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"허용되지 않은 파일 형식입니다. (허용: {allowed})",
      )
    return ext

  # ================================================================================================
  # 지식 파일 업로드
  # ------------------------------------------------------------------------------------------------
  # 파일을 저장소에 저장하고 관련 메타데이터를 DB에 기록
  # ================================================================================================
  @staticmethod
  def upload_knowledge_file(
    session: Session,
    knowledge_id: UUID,
    user_id: str,
    file: UploadFile,
  ) -> KnowledgeSourcesModel:
    # 지식 컨테이너(Knowledges) 존재 여부 확인
    knowledge = session.exec(select(KnowledgesModel).where(KnowledgesModel.id == knowledge_id, KnowledgesModel.user_id == user_id)).first()
    if not knowledge:
      raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="해당 지식 저장소를 찾을 수 없거나 권한이 없습니다.",
      )

    # 파일 확장자 검증
    if not file.filename:
      raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="파일명이 없습니다.",
      )

    _ = KnowledgeService.validate_file_extension(file.filename)

    # 사용자별 디렉토리 생성 및 파일 저장
    # 설정된 UPLOAD_DIR은 프로젝트 루트 기준입니다.
    # 안전을 위해 절대 경로로 변환하거나 프로젝트 루트를 기준으로 처리합니다.
    upload_base_path = Path(settings.UPLOAD_DIR).resolve()
    user_upload_path = upload_base_path / user_id
    user_upload_path.mkdir(parents=True, exist_ok=True)

    # 파일명 중복 방지를 위한 처리 (필요시 도입 가능하나 현재는 단순 저장)
    file_path = user_upload_path / file.filename

    try:
      with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    except Exception as e:
      raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"파일 저장 중 오류가 발생했습니다: {e!s}",
      ) from e

    # KnowledgeSourcesModel 레코드 생성 및 저장
    # storage_path는 추후 접근을 위해 상대 경로로 저장하는 것이 관례입니다.
    relative_storage_path = str(Path(user_id) / file.filename)

    source = KnowledgeSourcesModel(
      knowledge_id=knowledge_id,
      user_id=user_id,
      source_type=SourceType.FILE,
      display_name=file.filename,
      storage_path=relative_storage_path,
      file_size=file_path.stat().st_size,
      mime_type=file.content_type or "application/octet-stream",
      processing_status=ProcessingStatus.PENDING,
      created_at=datetime.now(UTC),
      updated_at=datetime.now(UTC),
    )

    session.add(source)
    session.commit()
    session.refresh(source)

    return source

  # ================================================================================================
  # 지식 소스 삭제
  # ------------------------------------------------------------------------------------------------
  # 실제 파일을 삭제하고 DB 레코드를 논리 삭제 상태로 변경
  # ================================================================================================
  @staticmethod
  def delete_knowledge_source(
    session: Session,
    knowledge_id: UUID,
    source_id: UUID,
    user_id: str,
  ) -> None:
    # 대상 소스 존재 여부 및 권한 확인
    source = KnowledgeService._get_owned_knowledge_source(
      session=session,
      knowledge_id=knowledge_id,
      source_id=source_id,
      user_id=user_id,
    )

    # 물리적 파일 삭제 (FILE 타입인 경우)
    if source.source_type == SourceType.FILE and source.storage_path:
      upload_base_path = Path(settings.UPLOAD_DIR).resolve()
      file_path = upload_base_path / source.storage_path
      try:
        if file_path.exists():
          file_path.unlink()
      except Exception as e:
        # 파일 삭제 실패는 로그만 남기고 DB 상태는 업데이트하도록 처리할 수도 있으나,
        # 여기서는 안정성을 위해 예외를 전파하거나 상세 에러를 기록합니다.
        raise HTTPException(
          status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
          detail=f"물리 파일 삭제 중 오류가 발생했습니다: {e!s}",
        ) from e

    # DB 소프트 삭제 기록
    source.deleted_at = datetime.now(UTC)
    source.updated_at = datetime.now(UTC)

    session.add(source)
    session.commit()

  # ================================================================================================
  # 다운로드 가능 여부 확인
  # ------------------------------------------------------------------------------------------------
  # 파일의 존재 여부와 권한을 확인하여 다운로드 가능한 경로를 반환
  # ================================================================================================
  @staticmethod
  def get_downloadable_knowledge_source(
    session: Session,
    knowledge_id: UUID,
    source_id: UUID,
    user_id: str,
  ) -> tuple[KnowledgeSourcesModel, Path]:
    source = KnowledgeService._get_owned_knowledge_source(
      session=session,
      knowledge_id=knowledge_id,
      source_id=source_id,
      user_id=user_id,
    )

    if source.source_type != SourceType.FILE:
      raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="파일 소스만 다운로드할 수 있습니다.",
      )

    if not source.storage_path:
      raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="업로드된 파일 경로를 찾을 수 없습니다.",
      )

    upload_base_path = Path(settings.UPLOAD_DIR).resolve()
    file_path = (upload_base_path / source.storage_path).resolve()

    # 저장소 루트 밖 경로 접근을 차단합니다.
    if upload_base_path not in file_path.parents:
      raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="잘못된 파일 경로입니다.",
      )

    if not file_path.exists() or not file_path.is_file():
      raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="업로드된 파일을 찾을 수 없습니다.",
      )

    return source, file_path
