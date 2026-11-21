"""Structured logging with request correlation IDs and secret redaction.

Stdlib ``logging`` only. JSON output in production, readable console output in
development. Every formatted line passes through ``redact`` so connection-string
passwords and ``password=...``-style secrets never reach log sinks.
"""

import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from app.core.config import LogFormat, Settings

REDACTED = "***"
NO_REQUEST_ID = "-"
REQUEST_ID_HEADER = "X-Request-ID"
# Structured fields that callers may pass via ``extra=`` and that JSON output includes.
EXTRA_FIELDS = ("method", "path", "status_code", "duration_ms")
CONSOLE_FORMAT = "%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s"
# uvicorn installs its own handlers; route them through ours instead.
UVICORN_LOGGERS = ("uvicorn", "uvicorn.error")
UVICORN_ACCESS_LOGGER = "uvicorn.access"

request_id_var: ContextVar[str] = ContextVar("request_id", default=NO_REQUEST_ID)

_URL_PASSWORD = re.compile(r"(?P<prefix>\b[a-zA-Z][a-zA-Z0-9+.\-]*://[^:/@\s]*:)[^@\s]+(?=@)")
_KEY_VALUE_SECRET = re.compile(
    r"(?i)(?P<prefix>\b(?:password|passwd|pwd|secret|token|api[_-]?key)\b\s*[=:]\s*)"
    r"[^\s,;&'\"]+"
)


def redact(text: str) -> str:
    """Mask credentials embedded in URLs or key=value pairs."""
    text = _URL_PASSWORD.sub(rf"\g<prefix>{REDACTED}", text)
    return _KEY_VALUE_SECRET.sub(rf"\g<prefix>{REDACTED}", text)


class RequestContextFilter(logging.Filter):
    """Attach the current request ID and active OpenTelemetry trace/span IDs."""

    def filter(self, record: logging.LogRecord) -> bool:
        from app.core.telemetry import get_current_trace_ids

        record.request_id = request_id_var.get()
        trace_id, span_id = get_current_trace_ids()
        if trace_id:
            record.trace_id = trace_id
        if span_id:
            record.span_id = span_id
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line; every string value is redacted."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", NO_REQUEST_ID),
        }
        for field in EXTRA_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        for otel_field in ("trace_id", "span_id"):
            if hasattr(record, otel_field):
                payload[otel_field] = getattr(record, otel_field)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(
            {k: redact(v) if isinstance(v, str) else v for k, v in payload.items()},
            default=str,
        )


class ConsoleFormatter(logging.Formatter):
    """Human-readable development format, redacted."""

    def __init__(self) -> None:
        super().__init__(CONSOLE_FORMAT)

    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def configure_logging(settings: Settings) -> None:
    """Install a single redacting stdout handler on the root logger (idempotent)."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter() if settings.effective_log_format is LogFormat.JSON else ConsoleFormatter()
    )
    handler.addFilter(RequestContextFilter())
    handler.set_name("opspilot")

    root = logging.getLogger()
    for existing in [h for h in root.handlers if h.get_name() == "opspilot"]:
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(settings.log_level)

    for name in (*UVICORN_LOGGERS, UVICORN_ACCESS_LOGGER):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
    # RequestContextMiddleware writes the access log (with request IDs); silence uvicorn's
    # duplicate. uvicorn only emits access lines when this logger has handlers.
    logging.getLogger(UVICORN_ACCESS_LOGGER).propagate = False
