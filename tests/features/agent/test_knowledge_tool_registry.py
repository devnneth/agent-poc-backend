from unittest.mock import MagicMock

from app.features.agent.root.tools.knowledge_tool_registry import KnowledgeToolRegistry


# ==================================================================================================
# 도구 레지스트리 캐시 테스트
# --------------------------------------------------------------------------------------------------
# 데이터 버전 변경이 없을 때 기존에 생성된 도구를 재사용하여 성능을 최적화하는지 검증함
# ==================================================================================================
def test_knowledge_tool_registry_reuses_cached_tools_when_version_is_unchanged():
  registry = KnowledgeToolRegistry()
  retrieval_service = MagicMock()
  retrieval_service.get_user_tool_version.return_value = "v1"
  retrieval_service.list_user_knowledges.return_value = [MagicMock()]

  first_result = registry.get_tools(MagicMock(), "user-1", "thread-1", retrieval_service)
  second_result = registry.get_tools(MagicMock(), "user-1", "thread-1", retrieval_service)

  assert first_result.tools is second_result.tools
  assert first_result.should_notify is True
  assert second_result.should_notify is False
  retrieval_service.list_user_knowledges.assert_called_once()


# ==================================================================================================
# 도구 레지스트리 갱신 테스트
# --------------------------------------------------------------------------------------------------
# 데이터 버전이 변경되면 캐시된 도구를 버리고 새로 생성하는지 검증함
# ==================================================================================================
def test_knowledge_tool_registry_rebuilds_tools_when_version_changes():
  registry = KnowledgeToolRegistry()
  retrieval_service = MagicMock()
  retrieval_service.get_user_tool_version.side_effect = ["v1", "v2"]
  retrieval_service.list_user_knowledges.side_effect = [[MagicMock()], [MagicMock(), MagicMock()]]

  first_result = registry.get_tools(MagicMock(), "user-1", "thread-1", retrieval_service)
  second_result = registry.get_tools(MagicMock(), "user-1", "thread-1", retrieval_service)

  assert first_result.tools is not second_result.tools
  assert second_result.should_notify is True
  assert retrieval_service.list_user_knowledges.call_count == 2
