import logging

from app.features.agent.state import RootState
from app.infrastructure.models.memo_model import MemoModel

logger = logging.getLogger(__name__)


def find_memo_in_state(state: RootState, memo_id: int) -> MemoModel | None:
  """RootState의 memo_list에서 특정 ID를 가진 메모를 찾습니다."""
  memo_list = state.get("memo_list") or []
  logger.info("memo_list: %s", memo_list)

  for memo in memo_list:
    current_id = memo["id"] if isinstance(memo, dict) else getattr(memo, "id", None)
    if current_id == memo_id:
      if isinstance(memo, dict):
        return MemoModel.model_validate(memo)
      return memo

  return None
