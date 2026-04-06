from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from enum import StrEnum

from sqlmodel import Session

from app.core.config.environment import settings
from app.core.logging import setup_logging
from app.features.knowledge.processing.odlh_pipeline.services.env_service import EnvService
from app.features.knowledge.processing.worker import KnowledgeProcessingWorker
from app.features.llm.embedding_service import EmbeddingService
from app.infrastructure.persistence.database import engine

logger = logging.getLogger(__name__)


# ==================================================================================================
# 워커 파이프라인 모듈
# --------------------------------------------------------------------------------------------------
# 워커 실행 시 선택할 수 있는 처리 파이프라인 이름을 정의합니다
# ==================================================================================================
class PipelineModule(StrEnum):
  BASIC = "basic"
  ODLH = "odlh"


# ==================================================================================================
# 워커 세션 빌드
# --------------------------------------------------------------------------------------------------
# RAG 워커의 각 작업 단위 실행을 위한 독립적인 데이터베이스 세션을 생성함
# ==================================================================================================
def _build_session() -> Session:
  return Session(engine)


# ==================================================================================================
# 처리 서비스 빌드
# --------------------------------------------------------------------------------------------------
# 선택된 파이프라인 모듈에 맞는 knowledge processing 서비스를 생성합니다
# ==================================================================================================
def _build_processing_service(
  embedding_service: EmbeddingService,
  pipeline_module: PipelineModule,
):
  if pipeline_module == PipelineModule.BASIC:
    from app.features.knowledge.processing.basic_pipeline.processing_service import KnowledgeProcessingService

    return KnowledgeProcessingService(embedding_service=embedding_service)

  if pipeline_module == PipelineModule.ODLH:
    from app.features.knowledge.processing.odlh_pipeline.processing_service import KnowledgeProcessingService

    return KnowledgeProcessingService(embedding_service=embedding_service)

  raise ValueError(f"지원하지 않는 파이프라인 모듈입니다: {pipeline_module}")


# ==================================================================================================
# 인자 파싱
# --------------------------------------------------------------------------------------------------
# 워커 실행 시 사용할 파이프라인 모듈을 CLI 인자로 해석합니다
# ==================================================================================================
def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="RAG knowledge processing worker")
  parser.add_argument(
    "--pipeline",
    choices=[module.value for module in PipelineModule],
    default=PipelineModule.ODLH.value,
    help="knowledge 처리에 사용할 파이프라인 모듈",
  )
  return parser.parse_args(argv)


# ==================================================================================================
# 파이프라인 사전 점검
# --------------------------------------------------------------------------------------------------
# odlh 워커는 시작 전에 hybrid backend 헬스체크를 통과해야 실제 실행으로 진입합니다
# ==================================================================================================
def _validate_pipeline_runtime_requirements(pipeline_module: PipelineModule) -> None:
  if pipeline_module != PipelineModule.ODLH:
    return

  EnvService().ensure_backend_available()


# ==================================================================================================
# 메인 엔트리포인트
# --------------------------------------------------------------------------------------------------
# RAG 백그라운드 작업을 처리하는 워커 프로세스를 시작하고 실행함
# ==================================================================================================
def main(argv: Sequence[str] | None = None) -> None:
  args = _parse_args(argv)
  pipeline_module = PipelineModule(args.pipeline)
  setup_logging(settings)
  _validate_pipeline_runtime_requirements(pipeline_module)

  embedding_service = EmbeddingService(provider=settings.RAG_EMBEDDING_PROVIDER)
  processing_service = _build_processing_service(embedding_service, pipeline_module)
  worker = KnowledgeProcessingWorker(
    session_factory=_build_session,
    processor=processing_service,
    concurrency=settings.RAG_WORKER_CONCURRENCY,
    poll_interval_seconds=settings.RAG_WORKER_POLL_INTERVAL_SECONDS,
  )

  logger.info(
    "Starting RAG worker with provider=%s pipeline_module=%s concurrency=%s poll_interval=%s",
    settings.RAG_EMBEDDING_PROVIDER,
    pipeline_module.value,
    settings.RAG_WORKER_CONCURRENCY,
    settings.RAG_WORKER_POLL_INTERVAL_SECONDS,
  )
  worker.run_forever()


if __name__ == "__main__":
  main()
