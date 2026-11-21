"""Provider-neutral read-only source-control interface and domain models."""

from datetime import datetime
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, Field


class ScmMode(StrEnum):
    MOCK = "mock"
    LIVE = "live"


class ScmAuthType(StrEnum):
    MOCK = "mock"
    GITHUB_APP = "github_app"
    PAT = "pat"


class ScmProviderError(RuntimeError):
    """Base error for source-control provider failures."""


class ScmAuthError(ScmProviderError):
    """Invalid, expired, or missing credentials (401)."""


class ScmPermissionError(ScmProviderError):
    """Token lacks required read permissions (403)."""


class ScmRateLimitError(ScmProviderError):
    """Provider API rate limit exceeded (429/403 rate-limit)."""


class ScmNotFoundError(ScmProviderError):
    """Repository or resource not found or not accessible (404)."""


class ScmUpstreamError(ScmProviderError):
    """Upstream provider 5xx or transport failure."""


class ScmConnectionCheck(BaseModel):
    ok: bool
    mode: ScmMode
    permission_summary: dict[str, str] = Field(default_factory=dict)
    rate_limit_remaining: int | None = None
    diagnostics: str = ""


class ScmRepository(BaseModel):
    full_name: str
    default_branch: str
    html_url: str
    private: bool


class ScmCommit(BaseModel):
    sha: str
    message: str
    author: str
    committed_at: datetime
    html_url: str
    repository: str


class ScmReview(BaseModel):
    author: str
    state: str
    submitted_at: datetime | None = None


class ScmPullRequest(BaseModel):
    number: int
    title: str
    state: str
    author: str
    created_at: datetime
    merged_at: datetime | None = None
    html_url: str
    repository: str
    reviews: list[ScmReview] = Field(default_factory=list)


class ScmDeployment(BaseModel):
    id: int
    environment: str
    state: str
    creator: str
    ref: str
    created_at: datetime
    html_url: str
    repository: str


class ScmPage[T](BaseModel):
    items: list[T]
    page: int
    per_page: int
    has_next: bool = False


class SourceControlProvider(Protocol):
    """Read-only source-control contract."""

    mode: ScmMode

    def test_connection(self) -> ScmConnectionCheck: ...

    def get_repository(self, owner: str, repo: str) -> ScmRepository: ...

    def list_commits(
        self,
        owner: str,
        repo: str,
        *,
        since: datetime,
        until: datetime,
        page: int = 1,
        per_page: int = 20,
    ) -> ScmPage[ScmCommit]: ...

    def list_pull_requests(
        self,
        owner: str,
        repo: str,
        *,
        since: datetime,
        until: datetime,
        page: int = 1,
        per_page: int = 20,
    ) -> ScmPage[ScmPullRequest]: ...

    def list_deployments(
        self,
        owner: str,
        repo: str,
        *,
        since: datetime,
        until: datetime,
        page: int = 1,
        per_page: int = 20,
    ) -> ScmPage[ScmDeployment]: ...
