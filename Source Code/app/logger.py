"""
Logging setup for File2MD.

Logs are stored in a per-user application data directory, never alongside
documents and never containing extracted document content.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from .config import APP_NAME, get_app_data_dir


_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_initialized = False


def get_log_dir() -> Path:
    """Return the directory where log files are written."""
    path = get_app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure root logging for the application.

    - Writes to a rotating log file in the user app data directory.
    - Also writes to stderr (so PyInstaller --windowed builds can still
      redirect to a console if launched from one).
    - Idempotent: calling it multiple times will not add duplicate handlers.
    """
    global _initialized
    logger = logging.getLogger(APP_NAME)
    if _initialized:
        return logger

    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    try:
        log_file = get_log_dir() / "file2md.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=512_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)
    except OSError:
        # If we cannot write to the log file (e.g. read-only home dir),
        # fall back to stderr only.
        pass

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(level)
    logger.addHandler(stream_handler)

    _initialized = True
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a child logger under the File2MD namespace."""
    setup_logging()
    if name and not name.startswith(APP_NAME):
        return logging.getLogger(f"{APP_NAME}.{name}")
    return logging.getLogger(name or APP_NAME)
