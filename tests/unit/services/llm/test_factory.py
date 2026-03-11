# pylint: disable=protected-access, import-outside-toplevel
import pytest

from app.infrastructure.llm.client.llm_provider_factory import LLMProviderFactory
from app.infrastructure.llm.providers.anthropic_impl import AnthropicImpl
from app.infrastructure.llm.providers.custom_impl import CustomImpl
from app.infrastructure.llm.providers.gemini_impl import GeminiImpl
from app.infrastructure.llm.providers.openai_impl import OpenAIImpl


def test_get_llm_client_default():
  """provider를 명시하지 않았을 때 기본 제공자(custom)가 반환되는지 테스트합니다."""
  client = LLMProviderFactory.get_client()
  assert isinstance(client, CustomImpl)


def test_get_llm_client_explicit():
  """명시적으로 지정한 제공자가 반환되는지 테스트합니다."""
  client = LLMProviderFactory.get_client(provider="anthropic")
  assert isinstance(client, AnthropicImpl)


def test_get_llm_client_custom():
  """Custom 제공자가 정상적으로 생성되는지 테스트합니다."""
  client = LLMProviderFactory.get_client(provider="custom")
  assert isinstance(client, CustomImpl)


def test_get_llm_client_gemini():
  """Gemini 제공자가 정상적으로 생성되는지 테스트합니다."""
  client = LLMProviderFactory.get_client(provider="gemini")
  assert isinstance(client, GeminiImpl)


def test_get_llm_client_invalid():
  """지원하지 않는 제공자 요청 시 ValueError가 발생하는지 테스트합니다."""
  with pytest.raises(ValueError, match="Unsupported LLM provider: unknown"):
    LLMProviderFactory.get_client(provider="unknown")


def test_get_llm_client_case_insensitive():
  """제공자 이름의 대소문자 구분이 없는지 테스트합니다."""
  client = LLMProviderFactory.get_client(provider="OpEnAI")
  assert isinstance(client, OpenAIImpl)
