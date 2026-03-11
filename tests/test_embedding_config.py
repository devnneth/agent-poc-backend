import asyncio
import logging
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from app.features.agent.settings import EMBEDDING_MODEL_SETTINGS
from app.features.llm.embedding_service import EmbeddingService

logging.basicConfig(level=logging.INFO)


async def test_embedding_service_settings():
  print("Testing EmbeddingService with different providers...")

  # Mocking EmbeddingClientFactory to avoid actual API calls
  import app.infrastructure.llm.client.embedding_provider_factory as factory

  factory.EmbeddingClientFactory.get_client = MagicMock()
  mock_client = AsyncMock()
  factory.EmbeddingClientFactory.get_client.return_value = mock_client

  providers = ["custom", "openai", "gemini"]

  for provider in providers:
    print(f"\n--- Testing provider: {provider} ---")
    service = EmbeddingService(provider=provider)

    expected_config = EMBEDDING_MODEL_SETTINGS[provider]
    print(f"Expected Model: {expected_config.name}")
    print(f"Expected Dimension: {expected_config.dimension}")

    assert service._model == expected_config.name
    assert service._dimension == expected_config.dimension

    # Test embedding call
    await service.embedding("Hello world")

    # Verify the call to client.embed
    _args, kwargs = mock_client.embed.call_args
    print(f"Actual Call Model: {kwargs.get('model')}")
    print(f"Actual Call Dimensions: {kwargs.get('dimensions')}")

    assert kwargs.get("model") == expected_config.name
    assert kwargs.get("dimensions") == expected_config.dimension

  print("\nAll tests passed!")


if __name__ == "__main__":
  asyncio.run(test_embedding_service_settings())
