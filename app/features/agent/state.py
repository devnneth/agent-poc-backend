from langchain.agents import AgentState

from app.features.agent.entity import ActionType
from app.features.agent.entity import DeleteResultType
from app.features.agent.entity import HITLResultType
from app.features.agent.entity import IntentType
from app.features.agent.entity import MemoExtractedInfo
from app.features.agent.entity import ScheduleExtractedInfo
from app.features.agent.entity import TodoExtractedInfo
from app.infrastructure.models.google_calendar_event_model import GoogleCalendarEventModel
from app.infrastructure.models.memo_model import MemoModel
from app.infrastructure.models.todo_model import TodoModel


class RootState(AgentState, total=False):
  intent: IntentType | None
  action: ActionType | None
  schedule_slots: ScheduleExtractedInfo | None
  todo_slots: TodoExtractedInfo | None
  memo_slots: MemoExtractedInfo | None
  schedule_list: list[GoogleCalendarEventModel] | None
  todo_list: list[TodoModel] | None
  memo_list: list[MemoModel] | None
  user_confirmed: HITLResultType | None
  delete_result: DeleteResultType | None
