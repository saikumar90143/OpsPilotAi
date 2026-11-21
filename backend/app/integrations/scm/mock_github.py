"""Deterministic local mock GitHub adapter (runs without credentials)."""

from datetime import UTC, datetime, timedelta

from app.integrations.scm.base import (
    ScmCommit,
    ScmConnectionCheck,
    ScmDeployment,
    ScmMode,
    ScmPage,
    ScmPullRequest,
    ScmRepository,
    ScmReview,
)


class MockGitHubAdapter:
    """Synthetic read-only GitHub adapter for local dev and automated tests."""

    mode: ScmMode = ScmMode.MOCK

    def test_connection(self) -> ScmConnectionCheck:
        return ScmConnectionCheck(
            ok=True,
            mode=self.mode,
            permission_summary={
                "contents": "read (mock)",
                "pull_requests": "read (mock)",
                "deployments": "read (mock)",
            },
            rate_limit_remaining=5000,
            diagnostics="Mock GitHub adapter active (synthetic local fixtures; not live).",
        )

    def get_repository(self, owner: str, repo: str) -> ScmRepository:
        return ScmRepository(
            full_name=f"{owner}/{repo}",
            default_branch="main",
            html_url=f"https://github.com/{owner}/{repo}",
            private=True,
        )

    def list_commits(
        self,
        owner: str,
        repo: str,
        *,
        since: datetime,
        until: datetime,
        page: int = 1,
        per_page: int = 20,
    ) -> ScmPage[ScmCommit]:
        anchor = until.astimezone(UTC) - timedelta(minutes=25)
        if anchor < since.astimezone(UTC):
            anchor = since.astimezone(UTC)
        commits = [
            ScmCommit(
                sha="a1b2c3d4e5f678901234567890abcdef12345678",
                message=f"feat({repo}): tune connection pool and retry timeout",
                author="alice-sre",
                committed_at=anchor,
                html_url=f"https://github.com/{owner}/{repo}/commit/a1b2c3d4e5f67890",
                repository=f"{owner}/{repo}",
            ),
            ScmCommit(
                sha="f0e1d2c3b4a5968778695a4b3c2d1e0f9a8b7c6d",
                message=f"chore({repo}): update dependency lockfile",
                author="bob-platform",
                committed_at=anchor - timedelta(hours=2),
                html_url=f"https://github.com/{owner}/{repo}/commit/f0e1d2c3b4a59687",
                repository=f"{owner}/{repo}",
            ),
        ]
        return ScmPage(items=commits[:per_page], page=page, per_page=per_page, has_next=False)

    def list_pull_requests(
        self,
        owner: str,
        repo: str,
        *,
        since: datetime,
        until: datetime,
        page: int = 1,
        per_page: int = 20,
    ) -> ScmPage[ScmPullRequest]:
        anchor = until.astimezone(UTC) - timedelta(minutes=30)
        if anchor < since.astimezone(UTC):
            anchor = since.astimezone(UTC)
        prs = [
            ScmPullRequest(
                number=142,
                title=f"Adjust {repo} HTTP client pool and circuit breaker",
                state="closed",
                author="alice-sre",
                created_at=anchor - timedelta(hours=3),
                merged_at=anchor,
                html_url=f"https://github.com/{owner}/{repo}/pull/142",
                repository=f"{owner}/{repo}",
                reviews=[
                    ScmReview(
                        author="carol-lead",
                        state="APPROVED",
                        submitted_at=anchor - timedelta(minutes=15),
                    )
                ],
            )
        ]
        return ScmPage(items=prs[:per_page], page=page, per_page=per_page, has_next=False)

    def list_deployments(
        self,
        owner: str,
        repo: str,
        *,
        since: datetime,
        until: datetime,
        page: int = 1,
        per_page: int = 20,
    ) -> ScmPage[ScmDeployment]:
        anchor = until.astimezone(UTC) - timedelta(minutes=15)
        if anchor < since.astimezone(UTC):
            anchor = since.astimezone(UTC)
        deployments = [
            ScmDeployment(
                id=9001,
                environment="production",
                state="success",
                creator="release-bot",
                ref="main",
                created_at=anchor,
                html_url=f"https://github.com/{owner}/{repo}/deployments",
                repository=f"{owner}/{repo}",
            )
        ]
        return ScmPage(items=deployments[:per_page], page=page, per_page=per_page, has_next=False)
