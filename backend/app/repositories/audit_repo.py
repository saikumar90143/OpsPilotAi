"""Append-only audit log repository with secret sanitization."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import NO_REQUEST_ID, redact, request_id_var
from app.models.audit_log import AuditLog

FORBIDDEN_AUDIT_KEYS = frozenset(
    {
        "password",
        "password_hash",
        "token",
        "access_token",
        "refresh_token",
        "csrf_token",
        "secret",
        "jwt_secret_key",
        "authorization",
        "cookie",
    }
)


def sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not metadata:
        return {}
    cleaned: dict[str, Any] = {}
    for key, value in metadata.items():
        if key.lower() in FORBIDDEN_AUDIT_KEYS:
            cleaned[key] = "***"
        elif isinstance(value, str):
            cleaned[key] = redact(value)
        elif isinstance(value, dict):
            cleaned[key] = sanitize_metadata(value)
        else:
            cleaned[key] = value
    return cleaned


def append_event(
    db: Session,
    *,
    action: str,
    organization_id: int | None = None,
    actor_user_id: int | None = None,
    target_type: str | None = None,
    target_id: str | int | None = None,
    ip_address: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    """Append an immutable audit record to the current session."""
    entry = AuditLog(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        request_id=request_id_var.get() or NO_REQUEST_ID,
        ip_address=ip_address,
        metadata_json=sanitize_metadata(metadata),
    )
    db.add(entry)
    return entry


def list_by_org(db: Session, *, organization_id: int, limit: int) -> list[AuditLog]:
    statement = (
        select(AuditLog)
        .where(AuditLog.organization_id == organization_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
    )
    return list(db.scalars(statement).all())
