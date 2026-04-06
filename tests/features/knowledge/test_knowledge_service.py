import io
from unittest.mock import MagicMock
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi import UploadFile

from app.features.knowledge.knowledge_file_service import KnowledgeService
from app.infrastructure.models.knowledge_model import KnowledgesModel
from app.infrastructure.models.knowledge_model import KnowledgeSourcesModel
from app.infrastructure.models.knowledge_model import ProcessingStatus
from app.infrastructure.models.knowledge_model import SourceType


# ==================================================================================================
# 허용 확장자 유효성 검사 테스트
# --------------------------------------------------------------------------------------------------
# 지원하는 파일 확장자에 대해 정상적으로 통과하는지 검증
# ==================================================================================================
def test_validate_file_extension_success():
  # settings.ALLOWED_EXTENSIONS: ["pdf", "epub", "txt"] (기본값)
  assert KnowledgeService.validate_file_extension("test.pdf") == "pdf"
  assert KnowledgeService.validate_file_extension("test.EPUB") == "epub"
  assert KnowledgeService.validate_file_extension("data.txt") == "txt"


# ==================================================================================================
# 미지원 확장자 차단 테스트
# --------------------------------------------------------------------------------------------------
# 지원하지 않는 확장자 업로드 시 400 에러를 반환하는지 검증
# ==================================================================================================
def test_validate_file_extension_fail():
  with pytest.raises(HTTPException) as excinfo:
    KnowledgeService.validate_file_extension("unsafe.exe")
  assert excinfo.value.status_code == 400
  assert "허용되지 않은 파일 형식" in str(excinfo.value.detail)


# ==================================================================================================
# 존재하지 않는 지식 저장소 업로드 테스트
# --------------------------------------------------------------------------------------------------
# 유효하지 않은 지식 저장소 ID로 업로드 시 404 에러를 반환하는지 검증
# ==================================================================================================
@patch("app.features.knowledge.knowledge_file_service.settings")
def test_upload_knowledge_file_no_knowledge(mock_settings):
  session = MagicMock()
  session.exec().first.return_value = None  # 검색 결과 없음

  knowledge_id = uuid4()
  user_id = "user-123"
  file = MagicMock(spec=UploadFile)
  file.filename = "test.pdf"

  with pytest.raises(HTTPException) as excinfo:
    KnowledgeService.upload_knowledge_file(session, knowledge_id, user_id, file)

  assert excinfo.value.status_code == 404
  assert "해당 지식 저장소를 찾을 수 없거나" in str(excinfo.value.detail)


# ==================================================================================================
# 지식 파일 업로드 성공 테스트
# --------------------------------------------------------------------------------------------------
# 파일 업로드 및 DB 기록 과정이 정상적으로 수행되는지 검증
# ==================================================================================================
@patch("app.features.knowledge.knowledge_file_service.settings")
@patch("app.features.knowledge.knowledge_file_service.shutil.copyfileobj")
def test_upload_knowledge_file_success(mock_copy, mock_settings, tmp_path):
  # Mocking settings
  mock_settings.UPLOAD_DIR = str(tmp_path)
  mock_settings.ALLOWED_EXTENSIONS = ["pdf"]

  # Mocking DB session & Knowledge object
  session = MagicMock()
  knowledge = KnowledgesModel(id=uuid4(), user_id="user-123", title="Test Knowledge")
  session.exec().first.return_value = knowledge

  # Mocking file
  file_content = b"fake pdf content"
  file = MagicMock(spec=UploadFile)
  file.filename = "test.pdf"
  file.content_type = "application/pdf"
  file.file = io.BytesIO(file_content)

  knowledge_id = knowledge.id
  user_id = "user-123"

  # Execute
  result = KnowledgeService.upload_knowledge_file(session, knowledge_id, user_id, file)

  # Verify
  assert result.display_name == "test.pdf"
  assert result.user_id == user_id
  assert result.knowledge_id == knowledge_id
  assert result.mime_type == "application/pdf"
  assert result.processing_status == ProcessingStatus.PENDING

  # Verify physical file existence (mocked dir)
  expected_path = tmp_path / user_id / "test.pdf"
  assert expected_path.exists()

  # DB session calls
  session.add.assert_called_once()
  session.commit.assert_called_once()
  session.refresh.assert_called_once()


# ==================================================================================================
# 지식 소스 삭제 성공 테스트
# --------------------------------------------------------------------------------------------------
# 지식 소스 삭제 시 실제 파일 삭제와 DB 소프트 삭제가 이루어지는지 검증
# ==================================================================================================
@patch("app.features.knowledge.knowledge_file_service.settings")
def test_delete_knowledge_source_success(mock_settings, tmp_path):
  user_id = "user-123"
  knowledge_id = uuid4()
  source_id = uuid4()
  filename = "test.txt"
  relative_path = f"{user_id}/{filename}"

  # Mock settings
  mock_settings.UPLOAD_DIR = str(tmp_path)

  # 물리 파일 생성
  user_dir = tmp_path / user_id
  user_dir.mkdir(parents=True)
  file_path = user_dir / filename
  file_path.write_text("hello")
  assert file_path.exists()

  # Mock DB session & Source object
  session = MagicMock()
  source = KnowledgeSourcesModel(
    id=source_id,
    knowledge_id=knowledge_id,
    user_id=user_id,
    source_type=SourceType.FILE,
    storage_path=relative_path,
    display_name=filename,
  )
  session.exec().first.return_value = source

  # Execute
  KnowledgeService.delete_knowledge_source(session, knowledge_id, source_id, user_id)

  # Verify physical file deletion
  assert not file_path.exists()

  # Verify DB status
  assert source.deleted_at is not None

  # DB session calls
  session.commit.assert_called_once()


# ==================================================================================================
# 미존재 지식 소스 삭제 테스트
# --------------------------------------------------------------------------------------------------
# 존재하지 않는 지식 소스 삭제 시도 시 404 에러를 반환하는지 검증
# ==================================================================================================
def test_delete_knowledge_source_not_found():
  session = MagicMock()
  session.exec().first.return_value = None

  knowledge_id = uuid4()
  source_id = uuid4()
  user_id = "user-123"

  with pytest.raises(HTTPException) as excinfo:
    KnowledgeService.delete_knowledge_source(session, knowledge_id, source_id, user_id)

  assert excinfo.value.status_code == 404
  assert "해당 지식 소스를 찾을 수 없거나" in str(excinfo.value.detail)


# ==================================================================================================
# 다운로드 가능 지식 소스 조회 테스트
# --------------------------------------------------------------------------------------------------
# 소유권 확인 후 실제 파일 경로와 소스 정보를 정상 반환하는지 검증
# ==================================================================================================
@patch("app.features.knowledge.knowledge_file_service.settings")
def test_get_downloadable_knowledge_source_success(mock_settings, tmp_path):
  user_id = "user-123"
  knowledge_id = uuid4()
  source_id = uuid4()
  filename = "manual.pdf"
  relative_path = f"{user_id}/{filename}"

  mock_settings.UPLOAD_DIR = str(tmp_path)

  user_dir = tmp_path / user_id
  user_dir.mkdir(parents=True)
  file_path = user_dir / filename
  file_path.write_bytes(b"pdf-content")

  session = MagicMock()
  source = KnowledgeSourcesModel(
    id=source_id,
    knowledge_id=knowledge_id,
    user_id=user_id,
    source_type=SourceType.FILE,
    storage_path=relative_path,
    display_name=filename,
    mime_type="application/pdf",
  )
  session.exec().first.return_value = source

  result_source, result_path = KnowledgeService.get_downloadable_knowledge_source(
    session=session,
    knowledge_id=knowledge_id,
    source_id=source_id,
    user_id=user_id,
  )

  assert result_source == source
  assert result_path == file_path.resolve()


# ==================================================================================================
# 지식 소스 다운로드 권한 테스트
# --------------------------------------------------------------------------------------------------
# 권한이 없거나 없는 소스 요청 시 404 에러를 반환하는지 검증
# ==================================================================================================
@patch("app.features.knowledge.knowledge_file_service.settings")
def test_get_downloadable_knowledge_source_not_found(mock_settings, tmp_path):
  mock_settings.UPLOAD_DIR = str(tmp_path)

  session = MagicMock()
  session.exec().first.return_value = None

  with pytest.raises(HTTPException) as excinfo:
    KnowledgeService.get_downloadable_knowledge_source(
      session=session,
      knowledge_id=uuid4(),
      source_id=uuid4(),
      user_id="user-123",
    )

  assert excinfo.value.status_code == 404
  assert "해당 지식 소스를 찾을 수 없거나" in str(excinfo.value.detail)


# ==================================================================================================
# 실제 파일 누락 소스 조회 테스트
# --------------------------------------------------------------------------------------------------
# DB에는 존재하나 실제 파일이 없는 경우 404 에러를 발생하는지 검증
# ==================================================================================================
@patch("app.features.knowledge.knowledge_file_service.settings")
def test_get_downloadable_knowledge_source_missing_file(mock_settings, tmp_path):
  user_id = "user-123"
  knowledge_id = uuid4()
  source_id = uuid4()
  filename = "missing.pdf"

  mock_settings.UPLOAD_DIR = str(tmp_path)

  session = MagicMock()
  session.exec().first.return_value = KnowledgeSourcesModel(
    id=source_id,
    knowledge_id=knowledge_id,
    user_id=user_id,
    source_type=SourceType.FILE,
    storage_path=f"{user_id}/{filename}",
    display_name=filename,
  )

  with pytest.raises(HTTPException) as excinfo:
    KnowledgeService.get_downloadable_knowledge_source(
      session=session,
      knowledge_id=knowledge_id,
      source_id=source_id,
      user_id=user_id,
    )

  assert excinfo.value.status_code == 404
  assert "업로드된 파일을 찾을 수 없습니다." in str(excinfo.value.detail)
