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
from app.features.llm.llm_service import LLMServiceFactory


@pytest.mark.asyncio
async def test_extract_relative_time_with_past_context():
  """'작년 일정을 알려줘' 검색 후 '지난달로 해줘' 입력 시 기간이 오늘 기준으로 올바르게 추출되는지 확인 (few-shot 테스트 모방)"""

  # 이전 대화 문맥 세팅 (작년 일정 검색함 -> 지난달로 변경 요청)
  state: RootState = {
    "action": ActionType.SEARCH,
    "schedule_slots": ScheduleExtractedInfo(start_at="2025-01-01T00:00:00", end_at="2025-12-31T23:59:59", query="작년 일정"),
    "messages": [HumanMessage(content="작년 일정을 알려줘"), AIMessage(content="작년 일정을 검색할까요?"), HumanMessage(content="지난달로 해줘")],
  }

  # 현재 시간이 2026-02-27T10:00:00 KST 인 상황에서 offset 모방 (사실 LLM에게 맡기는 것이나, 응답 값을 모킹하여 테스트)
  config: RunnableConfig = {"configurable": {"minutes_offset": 540}}

  mock_service = MagicMock()
  mock_model = MagicMock()
  mock_structured_llm = MagicMock()

  # LLM이 파싱하여 반환한 값 가정 (Case D에 따라 현재 2026년 2월 기준으로 지난달인 2026년 1월 한달을 추출해야 함)
  mock_response = ScheduleExtractedInfo(start_at="2026-01-01T00:00:00", end_at="2026-01-31T23:59:59", summary=None, query=None)
  mock_structured_llm.ainvoke = AsyncMock(return_value=mock_response)
  mock_structured_llm.with_config.return_value = mock_structured_llm
  mock_model.with_structured_output.return_value = mock_structured_llm
  mock_service.get_model_for_node.return_value = mock_model

  # Factory 패치
  with patch.object(LLMServiceFactory, "get_service", return_value=mock_service):
    result = await extract_information_node(state, config)
    slots = (result.update or {}).get("schedule_slots")
    assert isinstance(slots, ScheduleExtractedInfo)
    assert slots.start_at == "2026-01-01T00:00:00"
    assert slots.end_at == "2026-01-31T23:59:59"
