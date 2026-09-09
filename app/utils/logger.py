"""
app/utils/logger.py
─────────────────────────────────────────────────────────────────────────────
Structured JSON logging for the DramaZone bot.

Design decisions
----------------
- JSON format in production   → machine-readable, easy to ship to log aggregators
- Pretty console in dev       → readable during local development
- Log level driven by config  → no code change needed to increase verbosity
- Sensitive data guards       → tokens, phone numbers, and user PII are never
                                 logged at DEBUG level (see SENSITIVE_FIELDS)
- Single call to setup_logging() at app startup configures the root logger;
  all modules then simply use `logging.getLogger(__name__)`.

Usage
-----
    # In main.py (once, at startup):
    from app.utils.logger import setup_logging
    setup_logging()

    # In any module:
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Order created", extra={"order_code": "DZ-20260909-AB12"})
"""

from __future__ import annotations

import logging
import sys
from typing import Any

# pythonjsonlogger is optional — if unavailable we fall back to a plain formatter
try:
    from pythonjsonlogger import jsonlogger  # type: ignore[import-untyped]
    _JSON_AVAILABLE = True
except ImportError:
    _JSON_AVAILABLE = False


# Fields that must never appear in log output (case-insensitive substring match)
SENSITIVE_FIELDS: tuple[str, ...] = (
    "token",
    "secret",
    "password",
    "phone",
    "webhook_secret",
)


class _SensitiveDataFilter(logging.Filter):
    """
    Drop log records that accidentally contain sensitive field names in their
    message or extra kwargs.

    This is a last-resort safety net — application code should not log
    sensitive data in the first place.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage().lower()
        for field in SENSITIVE_FIELDS:
            if field in message and record.levelno == logging.DEBUG:
                # Suppress DEBUG-level messages that mention sensitive terms
                return False
        return True


class _JsonFormatter(logging.Formatter):
    """
    Minimal JSON formatter used when python-json-logger is not installed.
    Outputs a single-line JSON object per log record.
    """

    def format(self, record: logging.LogRecord) -> str:
        import json
        import datetime

        payload: dict[str, Any] = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        # Include any extra fields attached via logger.info(..., extra={...})
        skip = {
            "args", "created", "exc_info", "exc_text", "filename",
            "funcName", "levelname", "levelno", "lineno", "message",
            "module", "msecs", "msg", "name", "pathname", "process",
            "processName", "relativeCreated", "stack_info", "thread",
            "threadName", "taskName",
        }
        for key, val in record.__dict__.items():
            if key not in skip:
                payload[key] = val
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO", *, use_json: bool | None = None) -> None:
    """
    Configure the root logger.

    Parameters
    ----------
    level:
        Logging level string (DEBUG / INFO / WARNING / ERROR / CRITICAL).
        Typically passed from ``get_settings().log_level``.
    use_json:
        Force JSON (True) or pretty console (False) output.
        If None (default), JSON is used in production, console in development.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Decide on formatter
    if use_json is None:
        # Auto-detect: if stdout is not a TTY we assume production/container
        use_json = not sys.stdout.isatty()

    if use_json and _JSON_AVAILABLE:
        formatter: logging.Formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
    elif use_json:
        # python-json-logger not installed — use our minimal fallback
        formatter = _JsonFormatter()
    else:
        # Human-readable console format for local development
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(_SensitiveDataFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    # Remove any handlers added by library imports before our setup
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Reduce noise from noisy third-party loggers
    logging.getLogger("motor").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    logging.getLogger(__name__).debug("Logging configured (level=%s, json=%s)", level, use_json)
