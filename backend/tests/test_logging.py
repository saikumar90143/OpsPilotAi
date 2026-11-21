"""Structured log formatting and secret redaction."""

import json
import logging
import sys

from app.core.logging import (
    ConsoleFormatter,
    JsonFormatter,
    RequestContextFilter,
    redact,
    request_id_var,
)

SECRET = "hunter2-secret"


def _record(msg: str, *args: object, **extra: object) -> logging.LogRecord:
    record = logging.LogRecord("test", logging.INFO, __file__, 1, msg, args, None)
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_redact_masks_url_passwords_and_key_values():
    text = f"url=postgresql+psycopg://user:{SECRET}@db:5432/x password={SECRET} token: {SECRET}"
    redacted = redact(text)
    assert SECRET not in redacted
    assert "postgresql+psycopg://user:***@db:5432/x" in redacted


def test_redact_leaves_ordinary_text_alone():
    assert redact("GET /health/ready -> 200") == "GET /health/ready -> 200"


def test_json_formatter_includes_request_id_and_extras():
    token = request_id_var.set("req-123")
    try:
        record = _record("%s %s", "GET", "/x", method="GET", status_code=200)
        RequestContextFilter().filter(record)
    finally:
        request_id_var.reset(token)
    payload = json.loads(JsonFormatter().format(record))
    assert payload["request_id"] == "req-123"
    assert payload["message"] == "GET /x"
    assert payload["method"] == "GET"
    assert payload["status_code"] == 200
    assert payload["level"] == "INFO"


def test_formatters_redact_args_and_tracebacks():
    try:
        raise ValueError(f"cannot connect to postgresql+psycopg://u:{SECRET}@h/db")
    except ValueError:
        exc_info = sys.exc_info()
    record = _record("connecting with %s", f"password={SECRET}")
    record.exc_info = exc_info
    RequestContextFilter().filter(record)

    json_line = JsonFormatter().format(record)
    json.loads(json_line)  # still valid JSON after redaction
    assert SECRET not in json_line
    assert SECRET not in ConsoleFormatter().format(record)
