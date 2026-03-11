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
async def test_extract_this_month_info():
  """'이번달 일정을 알려줘' 입력 시 기간(시작, 종료일)이 올바르게 추출되는지에 대한 로직(모킹 테스트) 확인"""

  state: RootState = {"action": ActionType.SEARCH, "schedule_slots": ScheduleExtractedInfo(), "messages": [HumanMessage(content="이번달 일정을 알려줘")]}

  # 2026-02-27T16:25:11 (KST +09:00 = 2026-02-28 01:25:11 내일로 넘어감) -> 설정상 540분 오프셋
  config: RunnableConfig = {"configurable": {"minutes_offset": 540}}

  mock_service = MagicMock()
  mock_model = MagicMock()
  mock_structured_llm = MagicMock()

  # LLM이 파싱하여 반환한 값 가정 (2026년 2월 한달)
  mock_response = ScheduleExtractedInfo(start_at="2026-02-01T00:00:00", end_at="2026-02-28T23:59:59", summary=None, query="이번달 일정")
  mock_structured_llm.ainvoke = AsyncMock(return_value=mock_response)
  mock_structured_llm.with_config.return_value = mock_structured_llm
  mock_model.with_structured_output.return_value = mock_structured_llm
  mock_service.get_model_for_node.return_value = mock_model

  # Factory 패치
  with patch.object(LLMServiceFactory, "get_service", return_value=mock_service):
    result = await extract_information_node(state, config)
    slots = (result.update or {}).get("schedule_slots")
    assert isinstance(slots, ScheduleExtractedInfo)
    assert slots.start_at == "2026-02-01T00:00:00"
    assert slots.end_at == "2026-02-28T23:59:59"
    assert slots.summary is None
    assert slots.query == "이번달 일정"
