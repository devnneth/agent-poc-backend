import logging
from typing import Any
from typing import ClassVar

from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config.environment import settings
from app.features.agent.settings import CHAT_MODEL_SETTINGS
from app.infrastructure.llm.providers.anthropic_impl import AnthropicImpl
from app.infrastructure.llm.providers.custom_impl import CustomImpl
from app.infrastructure.llm.providers.gemini_impl import GeminiImpl
from app.infrastructure.llm.providers.llm_provider_interface import LLMProviderInterface
from app.infrastructure.llm.providers.openai_impl import OpenAIImpl

logger = logging.getLogger(__name__)


class LLMProviderFactory:
  """provider별 LLMProviderInterface 인스턴스를 관리하고 반환하는 싱글톤 팩토리"""

  _instances: ClassVar[dict[str, LLMProviderInterface]] = {}

  @classmethod
  def get_client(cls, provider: str = "custom") -> LLMProviderInterface:
    selected = provider.lower()
    if selected not in cls._instances:
      logger.info("[LLMProviderFactory] Creating new raw client for provider: %s", selected)
      cls._instances[selected] = cls._create_raw_client(selected)
    else:
      logger.debug("[LLMProviderFactory] Reusing cached raw client for provider: %s", selected)
    return cls._instances[selected]

  @classmethod
  def _create_raw_client(cls, provider: str) -> LLMProviderInterface:
    registry = {
      "custom": lambda: CustomImpl(
        base_url=settings.CUSTOM_BASE_URL,
        api_key=settings.CUSTOM_API_KEY,
        chat_url=settings.CUSTOM_CHAT_URL,
        embeddings_url=settings.CUSTOM_EMBEDDINGS_URL,
        rerank_url=settings.CUSTOM_RERANK_URL,
      ),
      "openai": lambda: OpenAIImpl(api_key=settings.OPENAI_API_KEY),
      "gemini": lambda: GeminiImpl(api_key=settings.GEMINI_API_KEY),
      "anthropic": lambda: AnthropicImpl(api_key=settings.ANTHROPIC_API_KEY),
    }
    factory = registry.get(provider)
    if not factory:
      raise ValueError(f"Unsupported LLM provider: {provider}")
    return factory()


class ChatModelFactory:
  """LangChain BaseChatModel 인스턴스를 캐싱하고 관리하는 싱글톤 팩토리"""

  _instances: ClassVar[dict[str, BaseChatModel]] = {}

  @classmethod
  def get_model(
    cls,
    provider: str = "custom",
    model_name: str | None = None,
    temperature: float = 0.0,
    streaming: bool = True,
    callbacks: Any | None = None,
    **kwargs: Any,
  ) -> BaseChatModel:
    resolved_provider = provider.lower()
    resolved_model_name = model_name or CHAT_MODEL_SETTINGS[resolved_provider]

    # 콜백이 있는 경우 캐싱을 우회하거나 키에 포함하여 매번 새로운 핸들러가 적용되도록 합니다.
    # 여기서는 콜백 유무를 키에 포함하여, 콜백이 있는 경우 호출 시마다 새로운 인스턴스가 생성되도록 유도합니다.
    # (핸들러 자체가 매번 새로 생성되므로 캐시 키가 달라져야 함)
    cb_key = "with_cb" if callbacks else "no_cb"
    key = f"{resolved_provider}:{resolved_model_name}:{temperature}:{streaming}:{cb_key}"

    if key not in cls._instances or callbacks:
      instance = cls._create_model_instance(
        provider=resolved_provider,
        model_name=resolved_model_name,
        temperature=temperature,
        streaming=streaming,
        callbacks=callbacks,
        **kwargs,
      )
      if not callbacks:
        cls._instances[key] = instance
      return instance
    else:
      return cls._instances[key]

  @classmethod
  def _create_model_instance(
    cls,
    provider: str,
    model_name: str,
    temperature: float = 0.0,
    streaming: bool = True,
    callbacks: Any | None = None,
    **kwargs: Any,
  ) -> BaseChatModel:
    client = LLMProviderFactory.get_client(provider)
    return client.get_langchain_model(
      model_name=model_name,
      temperature=temperature,
      streaming=streaming,
      callbacks=callbacks,
      **kwargs,
    )
