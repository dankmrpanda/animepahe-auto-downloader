"""
Logging configuration for AnimePahe Web Downloader.
"""

from __future__ import annotations


import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path


class StructuredJsonFormatter(logging.Formatter):
    """Compact JSON log formatter for local rotating files."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        for key in ("event", "task_id", "status", "reason", "path"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)

        return json.dumps(payload, ensure_ascii=True)


def setup_logging() -> None:
    """Configure console logging + rotating structured log files."""
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    log_dir = Path(
        os.environ.get("LOG_DIR", str(Path(__file__).resolve().parents[2] / "logs"))
    )
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    def _env_int(name: str, default: int) -> int:
        try:
            value = os.environ.get(name)
            return int(value) if value not in (None, "") else default
        except (TypeError, ValueError):
            return default

    max_bytes = _env_int("LOG_MAX_BYTES", 5 * 1024 * 1024)
    backup_count = _env_int("LOG_BACKUP_COUNT", 5)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    file_handler = RotatingFileHandler(
        filename=str(log_file),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(StructuredJsonFormatter())

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
