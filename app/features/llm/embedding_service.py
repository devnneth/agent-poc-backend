import logging
from typing import Any
from typing import overload

from pydantic import validate_call

from app.features.agent.settings import EMBEDDING_MODEL_SETTINGS
from app.features.agent.settings import EmbeddingModelName
from app.infrastructure.llm.client.embedding_provider_factory import EmbeddingClientFactory

logger = logging.getLogger(__name__)


class EmbeddingService:
  """공통 임베딩 생성 기능을 제공하는 서비스입니다."""

  def __init__(self, provider: str = "custom"):
    self._provider = provider
    self._llm_client = EmbeddingClientFactory.get_client(provider)

    # 설정에서 모델명과 차원수를 가져옵니다.
    config = EMBEDDING_MODEL_SETTINGS[provider]
    self._model: EmbeddingModelName = config.name  # type: ignore
    self._dimension = config.dimension

  @property
  def model_name(self) -> EmbeddingModelName:
    return self._model

  @overload
  async def embedding(self, texts: str, **kwargs: Any) -> list[float] | None: ...

  @overload
  async def embedding(self, texts: list[str], **kwargs: Any) -> list[list[float]]: ...

  @validate_call
  async def embedding(self, texts: str | list[str], **kwargs: Any) -> list[float] | list[list[float]] | None:
    """단일 또는 여러 텍스트에 대한 임베딩 벡터를 생성합니다."""
    if not texts:
      return None if isinstance(texts, str) else []

    is_single = isinstance(texts, str)
    query_texts = [texts] if is_single else texts

    # 기본 모델과 차원 설정이 kwargs에 없는 경우에만 사용합니다.
    options = {"model": self._model, "dimensions": self._dimension, **kwargs}

    try:
      embeddings = await self._llm_client.embed(texts=query_texts, **options)
      if is_single:
        if embeddings and len(embeddings) > 0:
          return embeddings[0]
        return None
      return embeddings or []
    except Exception as e:
      logger.error("Failed to generate embedding: %s", str(e))
      return None if is_single else []
