"""Phase 9 models: external action connectors (Jira/Slack) and human-gated ProposedAction."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ActionProviderType(StrEnum):
    JIRA = "jira"
    SLACK = "slack"


class ActionConnectorMode(StrEnum):
    MOCK = "mock"
    LIVE = "live"


class ActionType(StrEnum):
    JIRA_CREATE_ISSUE = "jira_create_issue"
    SLACK_POST_MESSAGE = "slack_post_message"


class ProposedActionStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"
    EXPIRED = "expired"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ExternalActionConnector(Base):
    __tablename__ = "external_action_connectors"
    __table_args__ = (UniqueConstraint("organization_id", "provider", "name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ActionConnectorMode.MOCK.value
    )
    base_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    allowed_targets_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    encrypted_credential: Mapped[str | None] = mapped_column(Text, nullable=True)
    permission_summary_json: Mapped[dict[str, str]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    last_test_status: Mapped[str] = mapped_column(String(24), nullable=False, default="untested")
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )


class ProposedAction(Base):
    __tablename__ = "proposed_actions"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key"),
        Index("ix_proposed_actions_org_status", "organization_id", "status"),
        Index("ix_proposed_actions_org_inc", "organization_id", "incident_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    investigation_id: Mapped[int | None] = mapped_column(
        ForeignKey("investigation_runs.id", ondelete="SET NULL"), nullable=True
    )
    connector_id: Mapped[int] = mapped_column(
        ForeignKey("external_action_connectors.id", ondelete="RESTRICT"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(48), nullable=False)
    target_system: Mapped[str] = mapped_column(String(24), nullable=False)
    target_destination: Mapped[str] = mapped_column(String(120), nullable=False)
    payload_preview_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_links_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    requested_by_type: Mapped[str] = mapped_column(String(16), nullable=False, default="user")
    requested_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=ProposedActionStatus.PROPOSED.value, index=True
    )
    approved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    execution_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    external_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    execution_result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    audit_metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )
