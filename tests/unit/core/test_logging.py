import logging
from pathlib import Path
from types import SimpleNamespace

from app.core.logging import build_log_file_path
from app.core.logging import build_logging_config
from app.core.logging import setup_logging


# ==================================================================================================
# 로그 디렉토리 생성 검증
# --------------------------------------------------------------------------------------------------
# 로그 파일 경로 계산 시 logs 디렉토리가 자동 생성되는지 확인합니다
# ==================================================================================================
def test_build_log_file_path_creates_log_directory(tmp_path: Path):
  log_dir = tmp_path / "logs"

  log_file_path = build_log_file_path(str(log_dir), "api")

  assert log_dir.is_dir()
  assert log_file_path == log_dir / "api.log"


# ==================================================================================================
# 일일 순환 로그 설정 검증
# --------------------------------------------------------------------------------------------------
# 일 단위 파일 로테이션 핸들러가 정상적으로 설정되는지 확인합니다
# ==================================================================================================
def test_build_logging_config_adds_daily_rotating_file_handler(tmp_path: Path):
  log_dir = tmp_path / "logs"

  config = build_logging_config("debug", str(log_dir), "rag-worker", 7)

  assert log_dir.is_dir()
  assert config["handlers"]["file"]["class"] == "logging.handlers.TimedRotatingFileHandler"
  assert config["handlers"]["file"]["filename"] == str(log_dir / "rag-worker.log")
  assert config["handlers"]["file"]["when"] == "midnight"
  assert config["handlers"]["file"]["backupCount"] == 7
  assert config["root"]["handlers"] == ["console", "file"]
  assert config["loggers"]["app"]["handlers"] == ["console", "file"]


# ==================================================================================================
# 파일 로깅 비활성화 검증
# --------------------------------------------------------------------------------------------------
# 파일 로깅 비활성화 시 콘솔 핸들러만 유지되는지 확인합니다
# ==================================================================================================
def test_build_logging_config_skips_file_handler_when_disabled(tmp_path: Path):
  log_dir = tmp_path / "logs"

  config = build_logging_config("info", str(log_dir), "api", 7, enable_file_logging=False)

  assert "file" not in config["handlers"]
  assert config["root"]["handlers"] == ["console"]
  assert config["loggers"]["app"]["handlers"] == ["console"]
  assert not log_dir.exists()


# ==================================================================================================
# 서비스 로그 기록 검증
# --------------------------------------------------------------------------------------------------
# 서비스 시작 후 첫 로그가 전용 파일에 정상 기록되는지 확인합니다
# ==================================================================================================
def test_setup_logging_writes_to_service_log_file(tmp_path: Path):
  log_dir = tmp_path / "logs"
  settings = SimpleNamespace(
    ENVIRONMENT="prod",
    LOG_LEVEL="INFO",
    LOG_DIR=str(log_dir),
    APP_LOG_NAME="api",
    LOG_BACKUP_COUNT=3,
  )

  setup_logging(settings)
  logger = logging.getLogger("app.test")
  logger.info("file logging smoke test")

  for handler in logging.getLogger("app").handlers:
    handler.flush()

  logging.shutdown()

  log_file_path = log_dir / "api.log"
  assert log_file_path.is_file()
  assert "file logging smoke test" in log_file_path.read_text(encoding="utf-8")


# ==================================================================================================
# 개발 환경 로그 설정 검증
# --------------------------------------------------------------------------------------------------
# dev 환경에서 파일 로그 생성이 생략되는지 확인합니다
# ==================================================================================================
def test_setup_logging_skips_service_log_file_in_dev(tmp_path: Path):
  log_dir = tmp_path / "logs"
  settings = SimpleNamespace(
    ENVIRONMENT="dev",
    LOG_LEVEL="INFO",
    LOG_DIR=str(log_dir),
    APP_LOG_NAME="api",
    LOG_BACKUP_COUNT=3,
  )

  setup_logging(settings)
  logger = logging.getLogger("app.test")
  logger.info("console only logging smoke test")

  for handler in logging.getLogger("app").handlers:
    handler.flush()

  logging.shutdown()

  assert all(not isinstance(handler, logging.FileHandler) for handler in logging.getLogger("app").handlers)
  assert not log_dir.exists()
