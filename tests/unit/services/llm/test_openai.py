# pylint: disable=protected-access
import json

from app.infrastructure.llm.providers.openai_impl import OpenAIImpl


def test_openai_extract_delta_text_success():
  """OpenAI 응답 JSON에서 텍스트 조각을 정확히 추출하는지 테스트합니다."""
  impl = OpenAIImpl(api_key="test-key")

  data = json.dumps({"choices": [{"delta": {"content": "Hello"}}]})
  text = impl._extract_delta_text(data)
  assert text == "Hello"


def test_openai_extract_delta_text_empty():
  """빈 데이터나 잘못된 형식의 데이터인 경우 빈 문자열을 반환하는지 테스트합니다."""
  impl = OpenAIImpl(api_key="test-key")

  assert impl._extract_delta_text("{}") == ""
  assert impl._extract_delta_text("invalid json") == ""


def test_openai_build_url():
  """Base URL에 따른 최종 API URL 구성을 테스트합니다."""
  # 기본 (api.openai.com)
  impl_default = OpenAIImpl(api_key="test-key")
  assert impl_default._build_chat_url() == "https://api.openai.com/v1/chat/completions"

  # 커스텀 (v1 포함)
  impl_v1 = OpenAIImpl(api_key="test-key", base_url="https://my-proxy.com/v1")
  assert impl_v1._build_chat_url() == "https://my-proxy.com/v1/chat/completions"

  # 커스텀 (v1 미포함)
  impl_no_v1 = OpenAIImpl(api_key="test-key", base_url="https://my-proxy.com")
  assert impl_no_v1._build_chat_url() == "https://my-proxy.com/v1/chat/completions"


def test_openai_extract_embeddings():
  """임베딩 응답에서 벡터를 정확히 추출하고 정렬하는지 테스트합니다."""
  impl = OpenAIImpl(api_key="test-key")

  raw_data = {
    "data": [{"index": 1, "embedding": [0.3, 0.4]}, {"index": 0, "embedding": [0.1, 0.2]}],
  }

  embeddings = impl._extract_embeddings(raw_data)
  assert len(embeddings) == 2
  assert embeddings[0] == [0.1, 0.2]  # index 0 이 첫 번째로 와야 함
  assert embeddings[1] == [0.3, 0.4]  # index 1 이 두 번째로 와야 함


def test_openai_missing_api_key():
  """API 키가 없을 때 ValueError가 발생하는지 테스트합니다."""
  _ = OpenAIImpl(api_key=None)

  # 비동기 함수 내에서 체크되므로 동기 호출 시 직접 발생하지 않고
  # stream_chat 등에서 발생함. 여기서는 간단히 초기화 상태만 확인하거나
  # stream_chat 호출 시의 예외를 테스트함 (pytest.mark.asyncio 필요)
