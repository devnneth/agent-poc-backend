import logging
from logging.config import dictConfig
from typing import Any


class CompactFormatter(logging.Formatter):
  """로거 이름을 축약하되, 짧은 이름은 보존하고 긴 이름만 15자 폭으로 맞춤."""

  def format(self, record: logging.LogRecord) -> str:
    orig_name = record.name
    # 15자가 넘는 경우에만 축약 처리
    if len(orig_name) > 15:
      record.name = f"{orig_name[:5]}...{orig_name[-7:]}"

    result = super().format(record)
    record.name = orig_name
    return result


def build_logging_config(level: str) -> dict[str, Any]:
  resolved_level = (level or "INFO").upper()
  return {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
      "default": {
        "()": CompactFormatter,
        "format": "%(asctime)s %(levelname)-8s [%(name)-15.15s] %(message)s",
        "datefmt": "%Y-%m-%d %H:%M:%S",
      },
    },
    "handlers": {
      "console": {
        "class": "logging.StreamHandler",
        "formatter": "default",
        "level": resolved_level,
      },
    },
    "root": {"level": resolved_level, "handlers": ["console"]},
    "loggers": {
      "app": {
        "handlers": ["console"],
        "level": resolved_level,
        "propagate": False,
      },
      "uvicorn": {
        "handlers": ["console"],
        "level": resolved_level,
        "propagate": False,
      },
      "uvicorn.error": {
        "handlers": ["console"],
        "level": resolved_level,
        "propagate": False,
      },
      "uvicorn.access": {
        "handlers": ["console"],
        "level": resolved_level,
        "propagate": False,
      },
    },
  }


def setup_logging(settings: Any) -> None:
  """Configure Python logging once per process using settings-defined log level."""
  log_level = getattr(settings, "LOG_LEVEL", "INFO")
  dictConfig(build_logging_config(log_level))
  logging.getLogger(__name__).debug("Logging configured with level %s", log_level)
