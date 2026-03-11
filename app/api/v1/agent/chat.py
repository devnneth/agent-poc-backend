import logging
from typing import Any

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from sqlmodel import Session

from app.api.common.exception_handlers import get_llm_error_info
from app.api.common.helper import extract_content
from app.api.common.helper import extract_interrupt
from app.api.common.request_entity import AgentChatRequest
from app.api.common.request_entity import AgentConfigurable
from app.api.common.response_entity import AgentResponseSSECategory
from app.api.common.response_entity import AgentResponseSSEPayload
from app.api.common.response_entity import AgentResponseSSEStatus
from app.api.common.response_entity import AgentResponseSSEType
from app.core.config.environment import settings
from app.features.agent.entity import HITLInterruptData
from app.features.agent.root.root_graph import get_router_graph
from app.features.agent.settings import SERVICE_SETTINGS as SS
from app.features.llm.embedding_service import EmbeddingService
from app.features.memos.memo_db_service import MemoDBService
from app.features.memos.memo_service import MemoService
from app.features.schedules.schedule_db_service import ScheduleDBService
from app.features.schedules.schedule_google_service import ScheduleGoogleService
from app.features.schedules.schedule_service import ScheduleService
from app.features.todos.todo_db_service import TodoDBService
from app.features.todos.todo_service import TodoService
from app.infrastructure.common.exceptions import LLMError
from app.infrastructure.google.calendar_client import GoogleCalendarClient
from app.infrastructure.llm.helpers.langfuse_callback import get_langfuse_callback
from app.infrastructure.persistence.database import get_session

router = APIRouter(prefix="/agent", tags=["agent"])
logger = logging.getLogger(__name__)


def _build_embedding_service(provider: str) -> EmbeddingService | None:
  """환경 설정에 따라 EmbeddingService 주입 여부를 결정합니다."""
  if not settings.EMBEDDING_ENABLED:
    return None
  return EmbeddingService(provider=provider)


def _build_schedule_service(payload: AgentChatRequest, db_session: Session) -> ScheduleService:
  """요청 단위 일정 서비스 인스턴스를 생성합니다."""
  calendar_client = GoogleCalendarClient(access_token=payload.google_calendar_token)
  return ScheduleService(
    db_service=ScheduleDBService(db_session),
    google_service=ScheduleGoogleService(calendar_client),
    embedding_service=_build_embedding_service(SS.schedule_service.embedding),
  )


def _build_todo_service(db_session: Session) -> TodoService:
  """요청 단위 할일 서비스 인스턴스를 생성합니다."""
  return TodoService(
    db_service=TodoDBService(db_session),
    embedding_service=_build_embedding_service(SS.todo_service.embedding),
  )


def _build_memo_service(db_session: Session) -> MemoService:
  """요청 단위 메모 서비스 인스턴스를 생성합니다."""
  return MemoService(
    db_service=MemoDBService(db_session),
    embedding_service=_build_embedding_service(SS.memo_service.embedding),
  )


def _build_runnable_config(
  payload: AgentChatRequest,
  db_session: Session,
  langfuse_handler: Any | None,
) -> RunnableConfig:
  """에이전트 실행용 RunnableConfig를 구성합니다."""
  configurable_dict = AgentConfigurable(
    **payload.model_dump(),
    thread_id=payload.session_id,
  ).model_dump()
  configurable_dict["schedule_service"] = _build_schedule_service(payload, db_session)
  configurable_dict["todo_service"] = _build_todo_service(db_session)
  configurable_dict["memo_service"] = _build_memo_service(db_session)

  return {
    "configurable": configurable_dict,
    "callbacks": [langfuse_handler] if langfuse_handler else [],
  }


async def _build_graph_input(
  graph: Any,
  payload: AgentChatRequest,
  config: RunnableConfig,
) -> dict[str, list[HumanMessage]] | Command:
  """현재 상태를 조회해 신규 대화/재개 대화 입력을 결정합니다."""
  current_state = await graph.aget_state(config)
  logger.info(f"⭐[UserRequestMessage] {payload.message}")

  if current_state.next:
    return Command(resume={"messages": [HumanMessage(content=payload.message)]})

  return {"messages": [HumanMessage(content=payload.message)]}


def _process_event_payload(
  kind: str,
  event_name: str,
  data: dict[str, Any],
  payload: AgentResponseSSEPayload,
  interrupt_message: Any,
  has_streamed_message_chunk: bool,
) -> bool:
  """개별 이벤트를 SSE 페이로드로 변환하며, 유효한 페이로드인 경우 True를 반환합니다."""
  success = False
  match kind:
    case "on_chat_model_start":
      payload.category = AgentResponseSSECategory.THINKING
      payload.status = AgentResponseSSEStatus.START
      logger.info(f"🤖[AI Thought] START {payload.content}")
      success = True

    case "on_chat_model_stream":
      if content := extract_content(data):
        payload.category = AgentResponseSSECategory.MESSAGE
        payload.status = AgentResponseSSEStatus.ING
        payload.content = content
        success = True

    case "on_chat_model_end":
      payload.status = AgentResponseSSEStatus.END
      if output := data.get("output"):
        payload.category = AgentResponseSSECategory.MESSAGE
        # 스트리밍 중 이미 본문을 모두 전달한 경우 종료 이벤트에서는 중복 본문을 내보내지 않습니다.
        payload.content = "" if has_streamed_message_chunk else getattr(output, "content", "")
        logger.info(f"🤖[AI Thought/Response] END {payload.content}")
      success = True

    case "on_tool_start":
      payload.category = AgentResponseSSECategory.TOOL
      payload.status = AgentResponseSSEStatus.START
      payload.content = f"도구 실행 중: {event_name}"
      logger.info(f"🛠️[Tool Start] {event_name} with inputs: {data.get('input')}")
      success = True

    case "on_tool_end":
      payload.category = AgentResponseSSECategory.TOOL
      payload.status = AgentResponseSSEStatus.END
      payload.content = "도구 실행 완료"
      logger.info(f"✅[Tool End] {event_name} result: {data.get('output')}")
      success = True

    case "on_custom_event":
      payload.category = AgentResponseSSECategory.HITL
      success = True

    case "on_interrupt":
      if isinstance(interrupt_message, HITLInterruptData):
        payload.category = interrupt_message.category
        payload.content = interrupt_message.message
        payload.metadata.update(interrupt_message.model_dump(exclude={"type", "message"}, exclude_none=True))
        success = True

  return success


async def _stream_agent_events(graph: Any, graph_input: Any, config: RunnableConfig):
  """그래프 이벤트를 SSE 페이로드로 변환해 스트리밍합니다."""
  try:
    # 재귀 제한 설정을 config에 추가
    config["recursion_limit"] = settings.AGENT_RECURSION_LIMIT
    has_streamed_message_chunk = False
    async for event in graph.astream_events(graph_input, config=config, version="v2"):
      # 스트리밍 비활성 이벤트는 생략하되, 인터럽트 이벤트는 항상 전달합니다.
      data = dict(event.get("data", {}))
      is_interrupt, interrupt_message = extract_interrupt(data)
      is_nostream = "nostream" in event.get("tags", [])
      if is_nostream and not is_interrupt:
        continue

      kind = "on_interrupt" if is_interrupt else event.get("event", "")
      metadata = event.get("metadata", {})
      node_name = metadata.get("node") or metadata.get("langgraph_node")

      # 내부 분석 노드는 사용자에게 노출하지 않습니다.
      if node_name in ["root_intent_node", "classify_schedule_action_node", "intent_shift_node"]:
        continue

      payload = AgentResponseSSEPayload(
        type=AgentResponseSSEType.DATA,
        category=AgentResponseSSECategory.NONE,
        status=AgentResponseSSEStatus.NONE,
        metadata={"node": node_name},
        content="",
      )

      # 헬퍼 함수를 통해 페이로드 구성
      is_hitl = "hitl" in event.get("tags", [])
      process_kind = "on_custom_event" if (kind == "on_custom_event" and is_hitl) else kind
      if process_kind == "on_chat_model_start":
        has_streamed_message_chunk = False

      if not _process_event_payload(
        process_kind,
        event.get("name", ""),
        data,
        payload,
        interrupt_message,
        has_streamed_message_chunk,
      ):
        continue

      if process_kind == "on_chat_model_stream" and payload.content:
        has_streamed_message_chunk = True

      yield f"data: {payload.model_dump_json()}\n\n"
  except Exception as e:
    logger.exception("Agent graph execution failed")

    content = "에이전트 실행 중 오류가 발생했습니다."
    metadata = {"error": str(e)}
    if isinstance(e, LLMError):
      content, _ = get_llm_error_info(e)
      if e.response_body:
        metadata["detail"] = e.response_body

    payload = AgentResponseSSEPayload(
      type=AgentResponseSSEType.DATA,
      category=AgentResponseSSECategory.ERROR,
      status=AgentResponseSSEStatus.END,
      content=content,
      metadata=metadata,
    )
    yield f"data: {payload.model_dump_json()}\n\n"


@router.post("/chat")
async def chat(payload: AgentChatRequest, db_session: Session = Depends(get_session)):
  """사용자 메시지를 라우터 에이전트 그래프에 전달하고 스트리밍 응답을 반환합니다."""
  if not payload.user_id:
    raise HTTPException(status_code=400, detail="user_id is required.")
  if not payload.session_id:
    raise HTTPException(status_code=400, detail="session_id is required.")

  # Langfuse 콜백 핸들러 설정
  langfuse_handler = get_langfuse_callback(
    config=settings,
    session_id=payload.session_id,
    user_id=payload.user_id,
    tags=[settings.ENVIRONMENT],
  )
  config = _build_runnable_config(payload, db_session, langfuse_handler)

  # 라우터 그래프를 지연 로드 (첫 호출 시 checkpointer DB 연결 및 컴파일)
  graph = await get_router_graph()
  graph_input = await _build_graph_input(graph, payload, config)

  return StreamingResponse(_stream_agent_events(graph, graph_input, config), media_type="text/event-stream")
