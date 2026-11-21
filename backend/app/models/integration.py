"""Tenant-specific integration configuration with encrypted secret storage."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

PROVIDER_MAX_LENGTH = 32
INTEGRATION_NAME_MAX_LENGTH = 100
ENDPOINT_TOKEN_MAX_LENGTH = 64
ENCRYPTED_SECRET_MAX_LENGTH = 512


class IntegrationProvider(StrEnum):
    ALERTMANAGER = "alertmanager"


class ConnectionStatus(StrEnum):
    SIMULATOR = "simulator"
    CONFIGURED = "configured"
    DISABLED = "disabled"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class IntegrationConfig(Base):
    __tablename__ = "integration_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(PROVIDER_MAX_LENGTH), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(INTEGRATION_NAME_MAX_LENGTH), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_simulator_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    webhook_endpoint_token: Mapped[str] = mapped_column(
        String(ENDPOINT_TOKEN_MAX_LENGTH), nullable=False, unique=True, index=True
    )
    encrypted_signing_secret: Mapped[str] = mapped_column(Text, nullable=False)
    previous_encrypted_signing_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    secret_rotated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rotation_grace_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )
