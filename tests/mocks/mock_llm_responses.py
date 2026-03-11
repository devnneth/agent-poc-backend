def get_mock_chat_stream():
  """모킹된 LLM 채팅 스트림 데이터를 반환합니다."""
  chunks = [
    '{"choices": [{"delta": {"content": "Hello"}}]}',
    '{"choices": [{"delta": {"content": " world!"}}]}',
    "[DONE]",
  ]
  return [f"data: {c}\n\n" for c in chunks]


def get_mock_embeddings_response():
  """모킹된 임베딩 응답 데이터를 반환합니다."""
  return {
    "data": [
      {"index": 0, "embedding": [0.1, 0.2, 0.3]},
      {"index": 1, "embedding": [0.4, 0.5, 0.6]},
    ],
  }


def get_mock_rerank_response():
  """모킹된 재순위화(Rerank) 응답 데이터를 반환합니다."""
  return {
    "results": [
      {"index": 1, "relevance_score": 0.9, "document": {"text": "doc 2"}},
      {"index": 0, "relevance_score": 0.3, "document": {"text": "doc 1"}},
    ],
  }
