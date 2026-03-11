import asyncio
from collections.abc import AsyncGenerator
from collections.abc import Generator
from contextlib import suppress
from typing import cast

import pytest
from httpx import ASGITransport
from httpx import AsyncClient

from app.core.config.environment import settings
from main import get_application
from supabase import Client
from tests.mocks.mock_supabase import get_mock_supabase_client


@pytest.fixture(scope="session")
def event_loop() -> Generator:
  """세션 범위의 비동기 이벤트 루프를 생성합니다."""
  loop = asyncio.get_event_loop_policy().new_event_loop()
  yield loop
  loop.close()


@pytest.fixture(scope="session")
def app():
  """테스트용 FastAPI 애플리케이션 인스턴스를 생성합니다."""
  _app = get_application()
  return _app


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
  """비동기 HTTP 테스트 클라이언트를 제공합니다."""
  async with AsyncClient(
    transport=ASGITransport(app=app),
    base_url="http://testserver",
    headers={"Content-Type": "application/json"},
  ) as ac:
    yield ac


@pytest.fixture(autouse=True)
def mock_supabase(monkeypatch):
  """Supabase 클라이언트를 모킹하여 실제 DB 연동 없이 테스트할 수 있게 합니다."""
  mock_client = get_mock_supabase_client()
  # 전역 수준의 supabase 클라이언트를 모킹합니다.
  # 임포트 방식(from ... import supabase)에 따라 여러 지점을 패치해야 할 수 있습니다.
  patch_targets = [
    "app.infrastructure.auth.supabase.SupabaseAuth._client_instance",
  ]

  for target in patch_targets:
    with suppress(ImportError, AttributeError):
      monkeypatch.setattr(target, mock_client)

  # 이미 초기화된 서비스 싱글톤들을 초기화하여
  # 매 테스트마다 새로운 모킹 클라이언트가 주입되도록 합니다.
  try:
    from app.features.auth.auth_service import AuthService
    from app.infrastructure.auth.google import GoogleAuth
    from app.infrastructure.auth.supabase import SupabaseAuth

    # 모든 싱글톤 인스턴스를 None으로 리셋
    AuthService._instance = None
    SupabaseAuth._instance = None
    SupabaseAuth._client_instance = cast(Client, mock_client)
    GoogleAuth._instance = None

  except (ImportError, AttributeError):
    pass

  return mock_client


@pytest.fixture
def mock_settings():
  """설정 값을 프로젝트 요구사항에 맞게 오버라이드할 때 사용합니다."""
  # 특정 테스트를 위해 설정을 재정의해야 할 경우 사용합니다.
  return settings
