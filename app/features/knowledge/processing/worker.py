from __future__ import annotations

import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC
from datetime import datetime
from uuid import UUID

from sqlalchemy.dialects import postgresql
from sqlmodel import Session
from sqlmodel import col
from sqlmodel import select

from app.core.config.environment import settings
from app.infrastructure.models.knowledge_model import KnowledgeSourcesModel
from app.infrastructure.models.knowledge_model import ProcessingStatus

logger = logging.getLogger(__name__)


# ==================================================================================================
# 지식 처리 워커
# --------------------------------------------------------------------------------------------------
# DB 폴링 기반으로 대기 중인 소스를 선점해 처리하는 백그라운드 워커입니다
# ==================================================================================================
class KnowledgeProcessingWorker:
  # ================================================================================================
  # 초기화
  # ------------------------------------------------------------------------------------------------
  # 폴링 주기 및 처리에 필요한 서비스를 설정하여 워커를 준비합니다
  # ================================================================================================
  def __init__(
    self,
    session_factory: Callable[[], Session],
    processor,
    concurrency: int | None = None,
    poll_interval_seconds: int | None = None,
  ):
    self._session_factory = session_factory
    self._processor = processor
    self._concurrency = concurrency or settings.RAG_WORKER_CONCURRENCY
    self._poll_interval_seconds = poll_interval_seconds or settings.RAG_WORKER_POLL_INTERVAL_SECONDS

  # ================================================================================================
  # 선점 쿼리 생성
  # ------------------------------------------------------------------------------------------------
  # 동시성 제어를 위해 처리할 대상을 선점하는 SQL 구문을 생성합니다
  # ================================================================================================
  @staticmethod
  def build_claim_statement(limit: int):
    return (
      select(KnowledgeSourcesModel)
      .where(
        KnowledgeSourcesModel.deleted_at == None,  # noqa: E711
        KnowledgeSourcesModel.processing_status == ProcessingStatus.PENDING,
      )
      .order_by(col(KnowledgeSourcesModel.created_at))
      .limit(limit)
      .with_for_update(skip_locked=True)
    )

  # ================================================================================================
  # 선점 쿼리 컴파일
  # ------------------------------------------------------------------------------------------------
  # PostgreSQL 기준 SQL 문자열을 반환합니다
  # ================================================================================================
  @staticmethod
  def compile_claim_statement(limit: int) -> str:
    statement = KnowledgeProcessingWorker.build_claim_statement(limit)
    return str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))

  # ================================================================================================
  # 대기 소스 선점
  # ------------------------------------------------------------------------------------------------
  # 처리 대기 중인 소스를 선점하고 즉시 작업 중 상태로 전이합니다
  # ================================================================================================
  def claim_pending_sources(self, session: Session, limit: int | None = None) -> list[KnowledgeSourcesModel]:
    claim_limit = limit or self._concurrency
    statement = self.build_claim_statement(claim_limit)
    sources = list(session.exec(statement).all())
    now = datetime.now(UTC)

    for source in sources:
      source.processing_status = ProcessingStatus.ING
      source.processing_started_at = now
      source.processing_completed_at = None
      source.processing_error_message = None
      source.updated_at = now
      session.add(source)

    if sources:
      session.commit()
      for source in sources:
        session.refresh(source)

    return sources

  # ================================================================================================
  # 단회 실행
  # ------------------------------------------------------------------------------------------------
  # 한 번 폴링하여 확보한 작업들을 순차적으로 처리합니다
  # ================================================================================================
  def run_once(self) -> int:
    with self._session_factory() as session:
      claimed_sources = self.claim_pending_sources(session)

    if not claimed_sources:
      return 0

    logger.info("knowledge source %s건을 선점해 처리를 시작합니다.", len(claimed_sources))

    with ThreadPoolExecutor(max_workers=self._concurrency) as executor:
      futures = [executor.submit(self._process_claimed_source, source.id) for source in claimed_sources]
      for future in futures:
        try:
          future.result()
        except Exception:
          logger.exception("knowledge source 처리 중 오류가 발생했습니다.")

    logger.info("이번 polling 주기에서 knowledge source %s건 처리를 마쳤습니다.", len(claimed_sources))
    return len(claimed_sources)

  # ================================================================================================
  # 무한 루프 실행
  # ------------------------------------------------------------------------------------------------
  # 지정된 간격으로 계속 폴링하며 작업을 수행합니다
  # ================================================================================================
  def run_forever(self) -> None:
    while True:
      processed_count = self.run_once()
      if processed_count == 0:
        time.sleep(self._poll_interval_seconds)

  # ================================================================================================
  # 선점 소스 처리
  # ------------------------------------------------------------------------------------------------
  # 확보된 개별 소스 문서에 대해 실제 처리 로직을 실행합니다
  # ================================================================================================
  def _process_claimed_source(self, source_id: UUID) -> None:
    with self._session_factory() as session:
      self._processor.process_source(session, source_id)
