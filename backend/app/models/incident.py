"""Incident persistence model and its domain vocabulary."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.incident_details import IncidentAffectedService, IncidentTag

TITLE_MAX_LENGTH = 180
SERVICE_MAX_LENGTH = 100
SOURCE_MAX_LENGTH = 50
ENUM_COLUMN_LENGTH = 20
ENVIRONMENT_MAX_LENGTH = 32
EXTERNAL_ID_MAX_LENGTH = 128
FINGERPRINT_MAX_LENGTH = 128
DEFAULT_SOURCE = "manual"


class Severity(StrEnum):
    """Technical and business impact of an incident (distinct from triage priority)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Environment(StrEnum):
    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"
    UNKNOWN = "unknown"


def utc_now() -> datetime:
    return datetime.now(UTC)


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assignee_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(TITLE_MAX_LENGTH), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    service: Mapped[str] = mapped_column(String(SERVICE_MAX_LENGTH), nullable=False, index=True)
    environment: Mapped[str] = mapped_column(
        String(ENVIRONMENT_MAX_LENGTH),
        nullable=False,
        default=Environment.UNKNOWN.value,
        index=True,
    )
    severity: Mapped[str] = mapped_column(
        String(ENUM_COLUMN_LENGTH), nullable=False, default=Severity.MEDIUM.value, index=True
    )
    status: Mapped[str] = mapped_column(
        String(ENUM_COLUMN_LENGTH), nullable=False, default=IncidentStatus.OPEN.value, index=True
    )
    source: Mapped[str] = mapped_column(
        String(SOURCE_MAX_LENGTH), nullable=False, default=DEFAULT_SOURCE
    )
    external_source_id: Mapped[str | None] = mapped_column(
        String(EXTERNAL_ID_MAX_LENGTH), nullable=True, index=True
    )
    fingerprint: Mapped[str | None] = mapped_column(
        String(FINGERPRINT_MAX_LENGTH), nullable=True, index=True
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    affected_service_rows: Mapped[list["IncidentAffectedService"]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="IncidentAffectedService.service_name",
    )
    tag_rows: Mapped[list["IncidentTag"]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="IncidentTag.tag",
    )

    @property
    def affected_services(self) -> list[str]:
        return [row.service_name for row in self.affected_service_rows]

    @property
    def tags(self) -> list[str]:
        return [row.tag for row in self.tag_rows]
