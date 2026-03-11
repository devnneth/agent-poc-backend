from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from app.features.agent.entity import ActionType
from app.features.agent.entity import ScheduleExtractedInfo
from app.features.agent.schedules.nodes.extract_information import extract_information_node
from app.features.agent.state import RootState


@pytest.mark.asyncio
async def test_extract_information_node_merging():
  # Setup state
  # User message 1: "내일 오전 10시에 일정 추가"
  # User message 2: "미팅이 있어. 메모에 참석자 확인하라고 해줘"
  state: RootState = {
    "action": ActionType.ADD,
    "schedule_slots": ScheduleExtractedInfo(start_at="2026-02-28T10:00:00", end_at="2026-02-28T11:00:00"),
    "messages": [
      HumanMessage(content="내일 오전 10시에 일정 추가"),
      AIMessage(content="제목과 내용을 알려주세요."),
      HumanMessage(content="미팅이 있어. 메모에 참석자 확인하라고 해줘"),
    ],
  }

  config: RunnableConfig = {"configurable": {"minutes_offset": 540}}

  # Mock LLM Service and Model
  from app.features.llm.llm_service import LLMServiceFactory

  mock_service = MagicMock()
  mock_model = MagicMock()

  # Simulate structured output
  # Before fix, the model might return summary=None
  mock_response = ScheduleExtractedInfo(summary="미팅", description="참석자 확인")

  # Mock llm.with_structured_output(ScheduleExtractedInfo)
  mock_structured_llm = MagicMock()
  # _apply_nostream creates a chain, we mock its invoke
  mock_structured_llm.ainvoke = AsyncMock(return_value=mock_response)
  mock_structured_llm.with_config.return_value = mock_structured_llm
  mock_model.with_structured_output.return_value = mock_structured_llm

  mock_service.get_model_for_node.return_value = mock_model

  # Patch the factory
  with patch.object(LLMServiceFactory, "get_service", return_value=mock_service):
    # Act
    result = await extract_information_node(state, config)

    # Assert
    slots = (result.update or {}).get("schedule_slots")
    assert isinstance(slots, ScheduleExtractedInfo)
    assert slots.summary == "미팅"
    assert slots.description == "참석자 확인"
    assert slots.start_at == "2026-02-28T10:00:00"  # Maintained from existing_slots


@pytest.mark.asyncio
async def test_extract_information_node_sync_end_at_on_start_at_change():
  # Case: Existing slots have Feb 28. New message changes start_at to Mar 1.
  # end_at should be updated to Mar 1 11:00:00 because it was Feb 28 11:00:00 (before start_at).
  state: RootState = {
    "action": ActionType.ADD,
    "schedule_slots": ScheduleExtractedInfo(summary="팀장 회의", start_at="2026-02-28T10:00:00", end_at="2026-02-28T11:00:00"),
    "messages": [
      HumanMessage(content="내일 오전 10시 팀장 회의 추가"),
      AIMessage(content="알겠습니다. 추가할까요?"),
      HumanMessage(content="아니 일요일로 바꿔줘"),
    ],
  }

  config: RunnableConfig = {"configurable": {"minutes_offset": 540}}

  from app.features.llm.llm_service import LLMServiceFactory

  mock_service = MagicMock()
  mock_model = MagicMock()

  # Simulate LLM extracting "Mar 1" for start_at and None for end_at
  mock_response = ScheduleExtractedInfo(start_at="2026-03-01T10:00:00", end_at=None)

  mock_structured_llm = MagicMock()
  mock_structured_llm.ainvoke = AsyncMock(return_value=mock_response)
  mock_structured_llm.with_config.return_value = mock_structured_llm
  mock_model.with_structured_output.return_value = mock_structured_llm
  mock_service.get_model_for_node.return_value = mock_model
  with patch.object(LLMServiceFactory, "get_service", return_value=mock_service):
    # Act
    result = await extract_information_node(state, config)

    # Assert
    slots = (result.update or {}).get("schedule_slots")
    assert isinstance(slots, ScheduleExtractedInfo)
    assert slots.start_at == "2026-03-01T10:00:00"
    assert slots.end_at == "2026-03-01T11:00:00"  # Should be synced!


@pytest.mark.asyncio
async def test_extract_information_node_delete_parses_explicit_schedule_id_from_latest_message():
  # Case: LLM이 schedule_id를 놓치더라도 최신 사용자 메시지의 "N번" 표현으로 대상 ID를 보정해야 한다.
  state: RootState = {
    "action": ActionType.DELETE,
    "schedule_slots": ScheduleExtractedInfo(),
    "messages": [
      HumanMessage(content="이번달 일정 확인좀 해줘"),
      AIMessage(content="검색 결과입니다. 32번 일정이 있습니다."),
      HumanMessage(content="32번 삭제해줘"),
    ],
  }

  config: RunnableConfig = {"configurable": {"minutes_offset": 540}}

  from app.features.llm.llm_service import LLMServiceFactory

  mock_service = MagicMock()
  mock_model = MagicMock()

  # 재현 조건: 구조화 출력이 최신 메시지에서 schedule_id를 올바르게 추출했다고 가정
  mock_response = ScheduleExtractedInfo(schedule_id=32, query=None)

  mock_structured_llm = MagicMock()
  mock_structured_llm.ainvoke = AsyncMock(return_value=mock_response)
  mock_structured_llm.with_config.return_value = mock_structured_llm
  mock_model.with_structured_output.return_value = mock_structured_llm
  mock_service.get_model_for_node.return_value = mock_model
  with patch.object(LLMServiceFactory, "get_service", return_value=mock_service):
    result = await extract_information_node(state, config)

    slots = (result.update or {}).get("schedule_slots")
    assert isinstance(slots, ScheduleExtractedInfo)
    assert slots.schedule_id == 32
