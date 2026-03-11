import logging
from typing import ClassVar

from app.infrastructure.llm.client.llm_provider_factory import LLMProviderFactory
from app.infrastructure.llm.providers.llm_provider_interface import LLMProviderInterface

logger = logging.getLogger(__name__)


class EmbeddingClientFactory:
  """provider별 LLMProviderInterface 인스턴스를 관리하고 반환하는 싱글톤 팩토리"""

  _instances: ClassVar[dict[str, LLMProviderInterface]] = {}

  @classmethod
  def get_client(cls, provider: str = "custom") -> LLMProviderInterface:
    key = provider.lower()
    if key not in cls._instances:
      logger.info("[EmbeddingClientFactory] Creating new embedding client for provider: %s", key)
      cls._instances[key] = LLMProviderFactory.get_client(key)
    else:
      logger.debug("[EmbeddingClientFactory] Reusing cached embedding client for provider: %s", key)
    return cls._instances[key]
