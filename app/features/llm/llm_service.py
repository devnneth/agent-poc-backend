import logging
from typing import Any
from typing import ClassVar

from langchain_core.language_models.chat_models import BaseChatModel

from app.features.agent.settings import AGENT_MODEL_SETTINGS
from app.infrastructure.llm.client.llm_provider_factory import ChatModelFactory

logger = logging.getLogger(__name__)


class LLMService:
  """에이전트별로 채팅 모델 및 로우 클라이언트를 제공하는 서비스입니다."""

  def __init__(self, provider: str = "custom"):
    self._provider = provider

  def get_model_for_node(self, node_name: str, callbacks: Any | None = None, **kwargs: Any) -> BaseChatModel:
    """에이전트 노드 설정을 기반으로 최적화된 LangChain 모델을 반환합니다."""
    node_settings = AGENT_MODEL_SETTINGS[node_name]
    provider = node_settings.get("provider", self._provider)
    temperature = node_settings.get("temperature", 0.0)
    streaming = node_settings.get("streaming", True)

    # 추가 kwargs가 있다면 노드 설정을 덮어씁니다.
    final_kwargs = {
      "temperature": kwargs.pop("temperature", temperature),
      "streaming": kwargs.pop("streaming", streaming),
      "callbacks": callbacks,
      **kwargs,
    }

    return ChatModelFactory.get_model(provider=provider, **final_kwargs)


class LLMServiceFactory:
  """provider별 LLMService 인스턴스를 관리하고 반환하는 싱글톤 팩토리"""

  _instances: ClassVar[dict[str, LLMService]] = {}

  @classmethod
  def get_service(cls, provider: str) -> LLMService:
    if provider not in cls._instances:
      cls._instances[provider] = LLMService(provider)
    logger.debug("[LLMServiceFactory] Return LLM service for provider: %s", provider)
    return cls._instances[provider]
