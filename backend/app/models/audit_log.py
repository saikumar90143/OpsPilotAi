"""Append-only security and domain audit log model."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

ACTION_MAX_LENGTH = 80
TARGET_TYPE_MAX_LENGTH = 50
TARGET_ID_MAX_LENGTH = 64
REQUEST_ID_MAX_LENGTH = 128
IP_ADDRESS_MAX_LENGTH = 64


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(ACTION_MAX_LENGTH), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(TARGET_TYPE_MAX_LENGTH), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(TARGET_ID_MAX_LENGTH), nullable=True)
    request_id: Mapped[str] = mapped_column(String(REQUEST_ID_MAX_LENGTH), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(IP_ADDRESS_MAX_LENGTH), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, index=True
    )
