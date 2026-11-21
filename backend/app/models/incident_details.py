"""Related incident domain records: timeline events, comments, evidence, services, tags."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.incident import SERVICE_MAX_LENGTH

if TYPE_CHECKING:
    from app.models.incident import Incident

TAG_MAX_LENGTH = 50
EVENT_TYPE_MAX_LENGTH = 64
TIMELINE_MSG_MAX_LENGTH = 500
EVIDENCE_KIND_MAX_LENGTH = 32
EVIDENCE_TITLE_MAX_LENGTH = 200
EVIDENCE_URI_MAX_LENGTH = 1000


class EvidenceKind(StrEnum):
    LOG = "log"
    METRIC = "metric"
    TRACE = "trace"
    COMMIT = "commit"
    RUNBOOK = "runbook"
    LINK = "link"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class IncidentAffectedService(Base):
    __tablename__ = "incident_affected_services"
    __table_args__ = (UniqueConstraint("incident_id", "service_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    service_name: Mapped[str] = mapped_column(
        String(SERVICE_MAX_LENGTH), nullable=False, index=True
    )

    incident: Mapped["Incident"] = relationship(back_populates="affected_service_rows")


class IncidentTag(Base):
    __tablename__ = "incident_tags"
    __table_args__ = (UniqueConstraint("incident_id", "tag"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tag: Mapped[str] = mapped_column(String(TAG_MAX_LENGTH), nullable=False, index=True)

    incident: Mapped["Incident"] = relationship(back_populates="tag_rows")


class IncidentTimelineEvent(Base):
    __tablename__ = "incident_timeline_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(
        String(EVENT_TYPE_MAX_LENGTH), nullable=False, index=True
    )
    message: Mapped[str] = mapped_column(String(TIMELINE_MSG_MAX_LENGTH), nullable=False)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, index=True
    )


class IncidentComment(Base):
    __tablename__ = "incident_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )


class IncidentEvidenceRef(Base):
    __tablename__ = "incident_evidence_refs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    added_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(EVIDENCE_KIND_MAX_LENGTH), nullable=False)
    title: Mapped[str] = mapped_column(String(EVIDENCE_TITLE_MAX_LENGTH), nullable=False)
    uri: Mapped[str | None] = mapped_column(String(EVIDENCE_URI_MAX_LENGTH), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, index=True
    )
