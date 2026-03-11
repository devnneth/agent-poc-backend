import logging

from app.features.agent.state import RootState
from app.infrastructure.models.todo_model import TodoModel

logger = logging.getLogger(__name__)


def find_todo_in_state(state: RootState, todo_id: int) -> TodoModel | None:
  """RootState의 todo_list에서 특정 ID를 가진 할일을 찾습니다."""
  todo_list = state.get("todo_list") or []
  logger.info(f"todo_list: {todo_list}")

  for todo in todo_list:
    current_id = todo["id"] if isinstance(todo, dict) else getattr(todo, "id", None)
    if current_id == todo_id:
      if isinstance(todo, dict):
        return TodoModel.model_validate(todo)
      return todo

  return None
