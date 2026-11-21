"""Persistent inbound event receipts, idempotency, retry state, and dead-lettering."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.integration import PROVIDER_MAX_LENGTH

IDEMPOTENCY_KEY_MAX_LENGTH = 255
EVENT_STATUS_MAX_LENGTH = 24
CORRELATION_ID_MAX_LENGTH = 128
LAST_ERROR_MAX_LENGTH = 500
EVENT_FINGERPRINT_MAX_LENGTH = 128


class InboundEventStatus(StrEnum):
    RECEIVED = "received"
    QUEUED = "queued"
    PROCESSING = "processing"
    PROCESSED = "processed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class InboundEvent(Base):
    __tablename__ = "inbound_events"
    __table_args__ = (UniqueConstraint("organization_id", "provider", "idempotency_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    integration_id: Mapped[int] = mapped_column(
        ForeignKey("integration_configs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(PROVIDER_MAX_LENGTH), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(IDEMPOTENCY_KEY_MAX_LENGTH), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(
        String(EVENT_FINGERPRINT_MAX_LENGTH), nullable=False, index=True
    )
    fingerprint: Mapped[str] = mapped_column(
        String(EVENT_FINGERPRINT_MAX_LENGTH), nullable=False, index=True
    )
    is_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    status: Mapped[str] = mapped_column(
        String(EVENT_STATUS_MAX_LENGTH),
        nullable=False,
        default=InboundEventStatus.RECEIVED.value,
        index=True,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    last_error: Mapped[str | None] = mapped_column(String(LAST_ERROR_MAX_LENGTH), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(CORRELATION_ID_MAX_LENGTH), nullable=False)
    incident_id: Mapped[int | None] = mapped_column(
        ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    raw_payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    normalized_payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, index=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dead_lettered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )
