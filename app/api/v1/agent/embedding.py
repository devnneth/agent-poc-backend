import logging

from fastapi import APIRouter

from app.api.common.request_entity import GoogleCalendarPayload
from app.api.common.request_entity import LLMEmbeddingRequest
from app.api.common.request_entity import MemoPayload
from app.api.common.request_entity import TodoPayload
from app.api.common.response import ok
from app.api.common.response_entity import CommonResponse
from app.features.agent.settings import SERVICE_SETTINGS as SS
from app.features.llm.embedding_service import EmbeddingService
from app.features.memos.memo_service import MemoService
from app.features.schedules.schedule_service import ScheduleService
from app.features.todos.todo_service import TodoService

router = APIRouter(prefix="/agent", tags=["agent"])
logger = logging.getLogger(__name__)


@router.post("/embedding", response_model=CommonResponse)
async def embedding(request: LLMEmbeddingRequest) -> CommonResponse:
  embedding = ""

  match request:
    case GoogleCalendarPayload():
      service = EmbeddingService(provider=SS.schedule_service.embedding)
      parsed_text = ScheduleService.format_schedule_for_embedding(
        summary=request.summary,
        description=request.description,
        start_at=request.start_at,
        end_at=request.end_at,
      )
      embedding = await service.embedding(parsed_text)
      pass
    case TodoPayload():
      service = EmbeddingService(provider=SS.todo_service.embedding)
      parsed_text = TodoService.format_todo_for_embedding(
        title=request.title,
        description=request.description,
        status=request.status,
        priority=request.priority,
        project=request.project,
      )
      embedding = await service.embedding(parsed_text)
    case MemoPayload():
      service = EmbeddingService(provider=SS.memo_service.embedding)
      parsed_text = MemoService.format_memo_for_embedding(
        title=request.title,
        content=request.content,
      )
      embedding = await service.embedding(parsed_text)

  return ok(embedding)
