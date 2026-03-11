from app.features.llm.llm_service import LLMServiceFactory


def test_llm_service_factory_singleton():
  """LLMServiceFactory가 동일한 provider에 대해 같은 인스턴스를 반환하는지 테스트합니다."""
  # Given & When
  service1 = LLMServiceFactory.get_service("openai")
  service2 = LLMServiceFactory.get_service("openai")
  service3 = LLMServiceFactory.get_service("custom")

  # Then
  assert service1 is service2
  assert service1 is not service3
  assert service1._provider == "openai"
  assert service3._provider == "custom"
