"""Deterministic secret and PII redaction for structured logs and evidence."""

import re
from typing import Any

REDACTED_SECRET = "[REDACTED_SECRET]"
REDACTED_PII = "[REDACTED_PII]"

SENSITIVE_KEY_NAMES = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "apikey",
        "authorization",
        "auth_header",
        "private_key",
        "client_secret",
        "signing_secret",
        "webhook_secret",
        "cookie",
        "set_cookie",
        "ssn",
        "credit_card",
        "card_number",
    }
)

_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # URI credentials: scheme://user:password@host
    (re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://[^:/\s]+:)([^@\s]+)(@)"), rf"\1{REDACTED_SECRET}\3"),
    # Bearer / Basic Authorization tokens
    (re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{8,}"), rf"\1 {REDACTED_SECRET}"),
    # GitHub tokens (classic, fine-grained, OAuth, app)
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{12,}\b"), REDACTED_SECRET),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{16,}\b"), REDACTED_SECRET),
    # Generic API keys & Slack/AWS/OpenAI-style tokens
    (
        re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16})\b"),
        REDACTED_SECRET,
    ),
    # JWTs (three base64url segments starting with eyJ)
    (
        re.compile(r"\beyJ[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}\b"),
        REDACTED_SECRET,
    ),
    # Inline key=value secrets
    (
        re.compile(
            r"(?i)\b(password|passwd|secret|api_key|token|private_key)\s*[:=]\s*([^\s,;\"']+)"
        ),
        rf"\1={REDACTED_SECRET}",
    ),
)

_PII_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Email addresses
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), REDACTED_PII),
    # US SSN pattern XXX-XX-XXXX
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), REDACTED_PII),
    # Credit-card-like 13-19 digit sequences (with optional spaces or dashes)
    (re.compile(r"\b(?:\d[ -]*?){13,19}\b"), REDACTED_PII),
)


def redact_text(value: str) -> str:
    """Redact known secrets and PII patterns from a text string."""
    result = value
    for pattern, replacement in _SECRET_PATTERNS:
        result = pattern.sub(replacement, result)
    for pattern, replacement in _PII_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def redact_value(value: Any, *, key_hint: str | None = None) -> Any:
    """Recursively redact secrets/PII from dicts, lists, and strings."""
    if key_hint is not None:
        normalized_key = key_hint.strip().lower().replace("-", "_")
        if normalized_key in SENSITIVE_KEY_NAMES or any(
            marker in normalized_key for marker in ("secret", "password", "token", "private_key")
        ):
            return REDACTED_SECRET
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {str(k): redact_value(v, key_hint=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    return value
