from unittest.mock import MagicMock
from unittest.mock import patch
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.api.common.jwt_request import jwt_required


# ==================================================================================================
# 업로드 라우트 확인
# --------------------------------------------------------------------------------------------------
# 지식 데이터 업로드를 위한 API 경로가 정상적으로 등록되어 있는지 검증함
# ==================================================================================================
@pytest.mark.asyncio
async def test_knowledge_upload_route_exists(client: AsyncClient):
  knowledge_id = uuid4()

  # JWT 인증 우회 및 서비스 모킹
  with (
    patch("app.api.common.jwt_request.jwt_required") as mock_jwt,
    patch("app.features.knowledge.knowledge_file_service.KnowledgeService.upload_knowledge_file") as mock_upload,
  ):
    mock_jwt.return_value = {"sub": "user-123"}
    mock_upload.return_value = MagicMock(display_name="test.pdf")

    # 파일 데이터 준비
    files = {"file": ("test.pdf", b"content", "application/pdf")}

    response = await client.post(f"/api/v1/knowledge/{knowledge_id}/upload", files=files)

    # 404가 아니면 라우트가 존재함 (인증이나 다른 이유로 에러가 날 순 있지만)
    assert response.status_code != 404


# ==================================================================================================
# 소스 삭제 라우트 확인
# --------------------------------------------------------------------------------------------------
# 지식 소스 삭제를 위한 API 경로가 정상적으로 등록되어 있는지 검증함
# ==================================================================================================
@pytest.mark.asyncio
async def test_knowledge_source_delete_route_exists(client: AsyncClient):
  knowledge_id = uuid4()
  source_id = uuid4()

  with (
    patch("app.api.common.jwt_request.jwt_required") as mock_jwt,
    patch("app.features.knowledge.knowledge_file_service.KnowledgeService.delete_knowledge_source") as mock_delete,
  ):
    mock_jwt.return_value = {"sub": "user-123"}
    mock_delete.return_value = None

    response = await client.delete(f"/api/v1/knowledge/{knowledge_id}/sources/{source_id}")

    assert response.status_code != 404


# ==================================================================================================
# 소스 다운로드 테스트
# --------------------------------------------------------------------------------------------------
# 지식 소스 파일 다운로드 시 실제 파일 스트림이 반환되는지 검증함
# ==================================================================================================
@pytest.mark.asyncio
async def test_knowledge_source_download_route_returns_file(client: AsyncClient, app):
  knowledge_id = uuid4()
  source_id = uuid4()

  app.dependency_overrides[jwt_required] = lambda: {"sub": "user-123"}

  try:
    with patch("app.api.v1.knowledge.download.KnowledgeService.get_downloadable_knowledge_source") as mock_download:
      mock_download.return_value = (
        MagicMock(display_name="test.pdf", mime_type="application/pdf"),
        __import__("pathlib").Path(__file__).resolve(),
      )

      response = await client.get(f"/api/v1/knowledge/{knowledge_id}/sources/{source_id}/download")

      assert response.status_code == 200
      assert response.headers["content-type"] == "application/pdf"
      assert 'attachment; filename="test.pdf"' in response.headers["content-disposition"]
  finally:
    app.dependency_overrides.clear()
