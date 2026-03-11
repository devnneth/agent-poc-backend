from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from app.features.llm.embedding_service import EmbeddingService
from app.infrastructure.llm.providers.llm_provider_interface import LLMProviderInterface


@pytest.fixture
def mock_llm_client():
  return MagicMock(spec=LLMProviderInterface)


@pytest.fixture
def embedding_service(mock_llm_client):
  with patch(
    "app.features.llm.embedding_service.EmbeddingClientFactory.get_client",
    return_value=mock_llm_client,
  ):
    return EmbeddingService(provider="custom")


@pytest.mark.asyncio
async def test_embedding_single_success(embedding_service, mock_llm_client):
  # Given
  text = "test text"
  mock_vector = [0.1, 0.2, 0.3]
  mock_llm_client.embed = AsyncMock(return_value=[mock_vector])

  # When
  result = await embedding_service.embedding(text)

  # Then
  assert result == mock_vector
  mock_llm_client.embed.assert_awaited_once_with(texts=[text], model=embedding_service._model, dimensions=embedding_service._dimension)


@pytest.mark.asyncio
async def test_embedding_single_empty_text(embedding_service, mock_llm_client):
  # Given
  text = ""

  # When
  result = await embedding_service.embedding(text)

  # Then
  assert result is None
  mock_llm_client.embed.assert_not_called()


@pytest.mark.asyncio
async def test_embedding_single_failure(embedding_service, mock_llm_client):
  # Given
  text = "test text"
  mock_llm_client.embed = AsyncMock(side_effect=Exception("API Error"))

  # When
  result = await embedding_service.embedding(text)

  # Then
  assert result is None


@pytest.mark.asyncio
async def test_embedding_multi_success(embedding_service, mock_llm_client):
  # Given
  texts = ["text1", "text2"]
  mock_vectors = [[0.1], [0.2]]
  mock_llm_client.embed = AsyncMock(return_value=mock_vectors)

  # When
  result = await embedding_service.embedding(texts)

  # Then
  assert result == mock_vectors
  mock_llm_client.embed.assert_awaited_once_with(texts=texts, model=embedding_service._model, dimensions=embedding_service._dimension)


@pytest.mark.asyncio
async def test_embedding_multi_empty_list(embedding_service, mock_llm_client):
  # Given
  texts = []

  # When
  result = await embedding_service.embedding(texts)

  # Then
  assert result == []
  mock_llm_client.embed.assert_not_called()


@pytest.mark.asyncio
async def test_embedding_multi_failure(embedding_service, mock_llm_client):
  # Given
  texts = ["text1", "text2"]
  mock_llm_client.embed = AsyncMock(side_effect=Exception("API Error"))

  # When
  result = await embedding_service.embedding(texts)

  # Then
  assert result == []
