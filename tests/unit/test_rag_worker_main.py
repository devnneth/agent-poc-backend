from __future__ import annotations

from unittest.mock import MagicMock
from unittest.mock import patch

from app.workers import rag_worker_main


# ==================================================================================================
# 워커 파이프라인 기본값 테스트
# --------------------------------------------------------------------------------------------------
# CLI 인자를 주지 않으면 기존 basic_pipeline 모듈이 기본 선택되는지 검증합니다
# ==================================================================================================
def test_parse_args_defaults_to_basic_pipeline():
  args = rag_worker_main._parse_args([])

  assert args.pipeline == rag_worker_main.PipelineModule.BASIC.value


# ==================================================================================================
# 워커 파이프라인 선택 전달 테스트
# --------------------------------------------------------------------------------------------------
# odlh 파이프라인 선택 시 해당 모듈 값이 처리 서비스 빌더로 전달되는지 검증합니다
# ==================================================================================================
def test_main_passes_selected_pipeline_module_to_processing_service_builder():
  embedding_service = object()
  build_processing_service = MagicMock(return_value="processor")
  worker = MagicMock()
  worker_class = MagicMock(return_value=worker)
  env_service = MagicMock()
  env_service_class = MagicMock(return_value=env_service)

  with (
    patch.object(rag_worker_main, "EnvService", env_service_class),
    patch.object(rag_worker_main, "setup_logging"),
    patch.object(rag_worker_main, "EmbeddingService", return_value=embedding_service),
    patch.object(rag_worker_main, "_build_processing_service", build_processing_service),
    patch.object(rag_worker_main, "KnowledgeProcessingWorker", worker_class),
  ):
    rag_worker_main.main(["--pipeline", rag_worker_main.PipelineModule.ODLH.value])

  env_service_class.assert_called_once_with()
  env_service.ensure_backend_available.assert_called_once_with()
  build_processing_service.assert_called_once_with(embedding_service, rag_worker_main.PipelineModule.ODLH)
  worker_class.assert_called_once()
  assert worker_class.call_args.kwargs["processor"] == "processor"
  worker.run_forever.assert_called_once()


# ==================================================================================================
# odlh 백엔드 사전 점검 실패 테스트
# --------------------------------------------------------------------------------------------------
# odlh 시작 전 backend check가 실패하면 워커를 만들지 않고 즉시 예외를 올리는지 검증합니다
# ==================================================================================================
def test_main_fails_fast_when_odlh_backend_is_unavailable():
  env_service = MagicMock()
  env_service.ensure_backend_available.side_effect = ValueError("백엔드 접근 실패")
  env_service_class = MagicMock(return_value=env_service)

  with (
    patch.object(rag_worker_main, "EnvService", env_service_class),
    patch.object(rag_worker_main, "setup_logging"),
    patch.object(rag_worker_main, "EmbeddingService") as embedding_service,
    patch.object(rag_worker_main, "_build_processing_service") as build_processing_service,
    patch.object(rag_worker_main, "KnowledgeProcessingWorker") as worker_class,
  ):
    try:
      rag_worker_main.main(["--pipeline", rag_worker_main.PipelineModule.ODLH.value])
    except ValueError as exc:
      assert str(exc) == "백엔드 접근 실패"
    else:
      raise AssertionError("odlh backend unavailable error was not raised")

  embedding_service.assert_not_called()
  build_processing_service.assert_not_called()
  worker_class.assert_not_called()
