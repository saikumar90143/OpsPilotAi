"""Tenant-scoped read-only GitHub connector configuration."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.integrations.scm.base import ScmAuthType, ScmMode

NAME_MAX_LENGTH = 100
MODE_MAX_LENGTH = 16
AUTH_TYPE_MAX_LENGTH = 24
ENDPOINT_TOKEN_MAX_LENGTH = 64
STATUS_MAX_LENGTH = 24
ERROR_MAX_LENGTH = 500


def _utc_now() -> datetime:
    return datetime.now(UTC)


class GitHubConnector(Base):
    __tablename__ = "github_connectors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH), nullable=False)
    mode: Mapped[str] = mapped_column(
        String(MODE_MAX_LENGTH), nullable=False, default=ScmMode.MOCK.value
    )
    auth_type: Mapped[str] = mapped_column(
        String(AUTH_TYPE_MAX_LENGTH), nullable=False, default=ScmAuthType.MOCK.value
    )
    github_app_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    github_installation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    encrypted_credential: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_webhook_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    webhook_endpoint_token: Mapped[str] = mapped_column(
        String(ENDPOINT_TOKEN_MAX_LENGTH), nullable=False, unique=True, index=True
    )
    service_repo_map_json: Mapped[dict[str, str]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_test_status: Mapped[str] = mapped_column(
        String(STATUS_MAX_LENGTH), nullable=False, default="untested"
    )
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(ERROR_MAX_LENGTH), nullable=True)
    permission_summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )
