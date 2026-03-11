# pylint: disable=protected-access
import json

import pytest

from app.infrastructure.llm.providers.gemini_impl import GeminiImpl


def test_gemini_extract_delta_text_success():
  """Gemini 응답 JSON에서 텍스트와 종료 여부를 정확히 추출하는지 테스트합니다."""
  impl = GeminiImpl(api_key="test-key")

  # 정상 데이터
  data = json.dumps(
    {"candidates": [{"content": {"parts": [{"text": "Hello, world!"}]}, "finishReason": ""}]},
  )
  text, is_done = impl._extract_delta_text(data)
  assert text == "Hello, world!"
  assert is_done is False

  # 종료 데이터
  data_done = json.dumps(
    {"candidates": [{"content": {"parts": [{"text": " Goodbye."}]}, "finishReason": "STOP"}]},
  )
  text, is_done = impl._extract_delta_text(data_done)
  assert text == " Goodbye."
  assert is_done is True


def test_gemini_extract_delta_text_error():
  """Gemini 에러 응답 처리 시 정확한 메시지를 반환하거나 예외를 던지는지 테스트합니다."""
  impl = GeminiImpl(api_key="test-key")

  error_data = json.dumps({"error": {"message": "Specific Gemini Error"}})

  with pytest.raises(ValueError, match="Specific Gemini Error"):
    impl._extract_delta_text(error_data)


def test_gemini_normalize_model():
  """모델 이름 정규화 로직을 테스트합니다."""
  impl = GeminiImpl(api_key="test-key")
  assert impl._normalize_model("gemini-1.5-flash") == "models/gemini-1.5-flash"
  assert impl._normalize_model("models/gemini-1.5-pro") == "models/gemini-1.5-pro"


@pytest.mark.asyncio
async def test_gemini_rerank_not_implemented():
  """Gemini의 rerank 미지원 예외 발생을 테스트합니다."""
  impl = GeminiImpl(api_key="test-key")
  with pytest.raises(NotImplementedError):
    await impl.rerank("query", ["doc1"])
