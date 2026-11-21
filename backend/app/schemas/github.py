"""Pydantic v2 schemas for the read-only GitHub connector and incident correlation."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.integrations.scm.base import ScmAuthType, ScmMode
from app.models.github_connector import NAME_MAX_LENGTH
from app.schemas.incident import EvidenceRead

REPO_PATTERN = r"^[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+$"


class GitHubConnectorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=NAME_MAX_LENGTH)
    mode: ScmMode = ScmMode.MOCK
    auth_type: ScmAuthType = ScmAuthType.MOCK
    github_app_id: str | None = Field(default=None, max_length=64)
    github_installation_id: str | None = Field(default=None, max_length=64)
    credential: str | None = Field(
        default=None, max_length=10_000, description="GitHub App PEM private key or PAT."
    )
    webhook_secret: str | None = Field(default=None, max_length=256)
    service_repo_map: dict[str, str] = Field(default_factory=dict)

    @field_validator("service_repo_map")
    @classmethod
    def _validate_repos(cls, value: dict[str, str]) -> dict[str, str]:
        import re

        cleaned: dict[str, str] = {}
        for svc, repo in value.items():
            r = repo.strip()
            if not re.fullmatch(REPO_PATTERN, r):
                raise ValueError(f"Repository '{repo}' must be in 'owner/repo' format")
            cleaned[svc.strip()] = r
        return cleaned


class GitHubConnectorUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=NAME_MAX_LENGTH)
    is_enabled: bool | None = None
    service_repo_map: dict[str, str] | None = None


class GitHubConnectorRead(BaseModel):
    """Redacted connector state — never exposes credentials or webhook secrets."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    name: str
    mode: ScmMode
    auth_type: ScmAuthType
    github_app_id: str | None
    github_installation_id: str | None
    has_credential: bool
    has_webhook_secret: bool
    webhook_path: str
    service_repo_map: dict[str, str]
    is_enabled: bool
    last_test_status: str
    last_test_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    permission_summary: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class GitHubConnectionTestRead(BaseModel):
    ok: bool
    mode: ScmMode
    permission_summary: dict[str, str]
    rate_limit_remaining: int | None
    diagnostics: str


class CorrelateGitHubRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: str | None = Field(default=None, pattern=REPO_PATTERN)
    lookback_hours: int = Field(default=24, ge=1, le=168)


class CorrelateGitHubResponse(BaseModel):
    mode: ScmMode
    repository: str
    disclaimer: str
    window_start: datetime
    window_end: datetime
    evidence_items: list[EvidenceRead]
