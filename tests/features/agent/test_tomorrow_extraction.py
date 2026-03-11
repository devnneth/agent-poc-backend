from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from app.features.agent.entity import ActionType
from app.features.agent.entity import ScheduleExtractedInfo
from app.features.agent.schedules.nodes.extract_information import extract_information_node
from app.features.agent.state import RootState
from app.features.llm.llm_service import LLMServiceFactory


@pytest.mark.asyncio
async def test_extract_tomorrow_info():
  """'내일 일정 추가' 입력 시 날짜가 올바르게 추출되는지에 대한 로직(모킹 테스트) 및 프롬프트 의도 준수 확인"""
  # 이 테스트는 실제 LLM을 호출하지는 않지만,
  # extract_information_node가 ExtractedInfo를 받아서 slots에 잘 반영하는지,
  # 그리고 프롬프트 변경 이후에도 기존 로직이 깨지지 않았는지 확인합니다.

  state: RootState = {"action": ActionType.ADD, "schedule_slots": ScheduleExtractedInfo(), "messages": [HumanMessage(content="내일 일정 추가")]}

  # 2026-02-27T16:25:11 기준 내일은 2026-02-28
  config: RunnableConfig = {"configurable": {"minutes_offset": 540}}

  mock_service = MagicMock()
  mock_model = MagicMock()
  mock_structured_llm = MagicMock()

  # LLM이 내일을 '2026-02-28T09:00:00'으로 추출했다고 가정
  mock_response = ScheduleExtractedInfo(start_at="2026-02-28T09:00:00", summary=None)
  mock_structured_llm.ainvoke = AsyncMock(return_value=mock_response)
  mock_structured_llm.with_config.return_value = mock_structured_llm
  mock_model.with_structured_output.return_value = mock_structured_llm
  mock_service.get_model_for_node.return_value = mock_model

  # Factory 패치
  with patch.object(LLMServiceFactory, "get_service", return_value=mock_service):
    result = await extract_information_node(state, config)
    slots = (result.update or {}).get("schedule_slots")
    assert isinstance(slots, ScheduleExtractedInfo)
    assert slots.start_at == "2026-02-28T09:00:00"
    assert slots.end_at == "2026-02-28T10:00:00"
    assert slots.summary is None


@pytest.mark.asyncio
async def test_extract_tomorrow_with_summary():
  """'내일 오후 2시 팀 회의'와 같이 제목이 섞인 경우 확인"""
  state: RootState = {"action": ActionType.ADD, "schedule_slots": ScheduleExtractedInfo(), "messages": [HumanMessage(content="내일 오후 2시 팀 회의")]}

  config: RunnableConfig = {"configurable": {"minutes_offset": 540}}

  mock_service = MagicMock()
  mock_model = MagicMock()
  mock_structured_llm = MagicMock()

  # LLM이 추출한 값 가정
  mock_response = ScheduleExtractedInfo(start_at="2026-02-28T14:00:00", summary="팀 회의")
  mock_structured_llm.ainvoke = AsyncMock(return_value=mock_response)
  mock_structured_llm.with_config.return_value = mock_structured_llm
  mock_model.with_structured_output.return_value = mock_structured_llm
  mock_service.get_model_for_node.return_value = mock_model

  with patch.object(LLMServiceFactory, "get_service", return_value=mock_service):
    result = await extract_information_node(state, config)
    slots = (result.update or {}).get("schedule_slots")
    assert isinstance(slots, ScheduleExtractedInfo)
    assert slots.start_at == "2026-02-28T14:00:00"
    assert slots.summary == "팀 회의"
    assert slots.end_at == "2026-02-28T15:00:00"
