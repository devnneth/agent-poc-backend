from unittest.mock import MagicMock
from unittest.mock import patch

from app.api.common.request_entity import AgentChatRequest
from app.api.v1.agent.chat import _build_memo_service
from app.api.v1.agent.chat import _build_schedule_service
from app.api.v1.agent.chat import _build_todo_service
from app.core.config.environment import settings


def test_build_services_skip_embedding_when_disabled():
  """EMBEDDING_ENABLED=false면 요청 단위 서비스에 EmbeddingService를 주입하지 않아야 합니다."""
  original = settings._settings.EMBEDDING_ENABLED
  settings._settings.EMBEDDING_ENABLED = False

  try:
    with patch("app.api.v1.agent.chat.EmbeddingService") as mock_embedding_service:
      payload = AgentChatRequest(
        user_id="user-123",
        session_id="session-123",
        message="일정 추가",
        language="ko",
        minutes_offset=540,
        google_calendar_token="token",
      )

      schedule_service = _build_schedule_service(payload, MagicMock())
      todo_service = _build_todo_service(MagicMock())
      memo_service = _build_memo_service(MagicMock())

      assert schedule_service._embedding_service is None
      assert todo_service._embedding_service is None
      assert memo_service._embedding_service is None
      mock_embedding_service.assert_not_called()
  finally:
    settings._settings.EMBEDDING_ENABLED = original
