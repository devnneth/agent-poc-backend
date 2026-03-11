# pylint: disable=protected-access
import json

import pytest

from app.infrastructure.llm.providers.anthropic_impl import AnthropicImpl


def test_anthropic_extract_delta_text_success():
  """Anthropic 응답 JSON에서 텍스트와 종료 여부를 정확히 추출하는지 테스트합니다."""
  impl = AnthropicImpl(api_key="test-key")

  # 텍스트 조각 데이터
  data = json.dumps(
    {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hello"}},
  )
  text, is_done = impl._extract_delta_text(data)
  assert text == "Hello"
  assert is_done is False

  # 종료 데이터
  data_done = json.dumps({"type": "message_stop"})
  text, is_done = impl._extract_delta_text(data_done)
  assert text == ""
  assert is_done is True


def test_anthropic_extract_delta_text_error():
  """Anthropic 에러 응답 처리 시 정확한 메시지를 반환하거나 예외를 던지는지 테스트합니다."""
  impl = AnthropicImpl(api_key="test-key")

  error_data = json.dumps({"type": "error", "error": {"message": "Overloaded"}})

  with pytest.raises(ValueError, match="Overloaded"):
    impl._extract_delta_text(error_data)


@pytest.mark.asyncio
async def test_anthropic_embed_not_implemented():
  """Anthropic의 embed 미지원 예외 발생을 테스트합니다."""
  impl = AnthropicImpl(api_key="test-key")
  with pytest.raises(NotImplementedError):
    await impl.embed(["text"])
