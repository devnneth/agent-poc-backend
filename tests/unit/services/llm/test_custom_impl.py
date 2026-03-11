# pylint: disable=protected-access
from app.infrastructure.llm.providers.custom_impl import CustomImpl


def test_custom_build_url():
  """커스텀 URL 구성 로직을 테스트합니다."""
  impl = CustomImpl(
    base_url="https://llm.internal",
    chat_url="/chat",
    rerank_url="https://rerank.external/v1/rerank",
  )

  # 상대 경로 결합
  assert impl._build_chat_url() == "https://llm.internal/chat"
  # 절대 경로 유지
  assert impl._build_rerank_url() == "https://rerank.external/v1/rerank"
  # 기본값 결합
  assert impl._build_embeddings_url() == "https://llm.internal/v1/embeddings"


def test_custom_extract_rerank_results():
  """Rerank 응답에서 결과를 정확히 추출하고 매핑하는지 테스트합니다."""
  impl = CustomImpl(base_url="https://test", api_key="test")

  docs = ["첫 번째 문서", "두 번째 문서"]
  raw_data = {"results": [{"index": 1, "relevance_score": 0.9}, {"index": 0, "score": 0.8}]}

  results = impl._extract_rerank_results(raw_data, docs)
  assert len(results) == 2

  # index 1 (두 번째 문서) 검증
  assert results[0]["index"] == 1
  assert results[0]["score"] == 0.9
  assert results[0]["text"] == "두 번째 문서"

  # index 0 (첫 번째 문서) 검증
  assert results[1]["index"] == 0
  assert results[1]["score"] == 0.8
  assert results[1]["text"] == "첫 번째 문서"


def test_custom_require_base_url():
  """Custom제공자에서 base_url 누락 시 예외 발생을 확인합니다 (OpenAICompatibleImpl 로직)."""
  # 팩토리나 초기화 단계에서는 예외가 발생하지 않지만
  # stream_chat 등 실제 호출 시 검증함.
  # 여기서는 초기화 및 속성 설정만 확인.
  impl = CustomImpl(base_url=None, api_key="test")
  assert impl._require_base_url is True
