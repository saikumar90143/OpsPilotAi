"""Read-only GitHub REST API client (GitHub App installation or fine-grained PAT)."""

import time
from datetime import UTC, datetime
from typing import Any

import httpx2 as httpx
import jwt

from app.integrations.scm.base import (
    ScmAuthError,
    ScmAuthType,
    ScmCommit,
    ScmConnectionCheck,
    ScmDeployment,
    ScmMode,
    ScmNotFoundError,
    ScmPage,
    ScmPermissionError,
    ScmProviderError,
    ScmPullRequest,
    ScmRateLimitError,
    ScmRepository,
    ScmReview,
    ScmUpstreamError,
)

GITHUB_API_VERSION = "2022-11-28"
MAX_RETRIES = 2


def _parse_iso(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _has_next_page(link_header: str | None) -> bool:
    if not link_header:
        return False
    return 'rel="next"' in link_header


class GitHubClient:
    """Read-only GitHub client with ETag caching, pagination, rate-limit handling, and retries."""

    mode: ScmMode = ScmMode.LIVE

    def __init__(
        self,
        *,
        auth_type: ScmAuthType,
        credential: str,
        app_id: str | None = None,
        installation_id: str | None = None,
        base_url: str = "https://api.github.com",
        timeout_seconds: int = 10,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._auth_type = auth_type
        self._credential = credential
        self._app_id = app_id
        self._installation_id = installation_id
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._transport = transport
        self._etag_cache: dict[str, tuple[str, Any, dict[str, str]]] = {}
        self._installation_token: str | None = None
        self._installation_permissions: dict[str, str] = {}

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self._base_url,
            timeout=self._timeout,
            transport=self._transport,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": GITHUB_API_VERSION,
                "User-Agent": "OpsPilot-AI-ReadOnly/0.1",
            },
        )

    def _get_bearer_token(self) -> str:
        if self._auth_type is ScmAuthType.PAT:
            return self._credential
        if self._installation_token:
            return self._installation_token
        if not self._app_id or not self._installation_id:
            raise ScmAuthError("GitHub App requires both app_id and installation_id")

        now = int(time.time())
        app_jwt = jwt.encode(
            {"iat": now - 60, "exp": now + 540, "iss": self._app_id},
            self._credential,
            algorithm="RS256",
        )
        with self._client() as client:
            resp = client.post(
                f"/app/installations/{self._installation_id}/access_tokens",
                headers={"Authorization": f"Bearer {app_jwt}"},
            )
        if resp.status_code == 401:
            raise ScmAuthError("GitHub App JWT authentication failed")
        if resp.status_code == 403:
            raise ScmPermissionError("GitHub App lacks installation token permission")
        if resp.status_code == 404:
            raise ScmNotFoundError("GitHub App installation not found")
        if resp.status_code >= 400:
            raise ScmUpstreamError(f"GitHub App token exchange failed ({resp.status_code})")

        data = resp.json()
        self._installation_token = str(data["token"])
        raw_perms = data.get("permissions") or {}
        self._installation_permissions = {str(k): str(v) for k, v in raw_perms.items()}
        return self._installation_token

    def _get(
        self, path: str, *, params: dict[str, Any] | None = None
    ) -> tuple[Any, dict[str, str]]:
        token = self._get_bearer_token()
        cache_key = f"{path}?{sorted((params or {}).items())}"
        cached = self._etag_cache.get(cache_key)

        headers: dict[str, str] = {"Authorization": f"Bearer {token}"}
        if cached is not None:
            headers["If-None-Match"] = cached[0]

        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                with self._client() as client:
                    resp = client.get(path, params=params, headers=headers)
            except httpx.TransportError as exc:
                last_exc = exc
                if attempt < MAX_RETRIES:
                    time.sleep(0.1 * (2**attempt))
                    continue
                raise ScmUpstreamError(f"GitHub transport failure: {type(exc).__name__}") from exc

            if resp.status_code == 304 and cached is not None:
                return cached[1], cached[2]

            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            if resp.status_code == 401:
                raise ScmAuthError("GitHub authentication failed (401)")
            if resp.status_code == 403:
                if resp_headers.get("x-ratelimit-remaining") == "0":
                    if attempt < MAX_RETRIES:
                        time.sleep(0.1 * (2**attempt))
                        continue
                    raise ScmRateLimitError("GitHub API rate limit exceeded")
                raise ScmPermissionError("GitHub token lacks required read permissions (403)")
            if resp.status_code == 404:
                raise ScmNotFoundError(f"GitHub resource not found: {path}")
            if resp.status_code == 429:
                if attempt < MAX_RETRIES:
                    time.sleep(0.1 * (2**attempt))
                    continue
                raise ScmRateLimitError("GitHub API rate limit exceeded (429)")
            if resp.status_code >= 500:
                if attempt < MAX_RETRIES:
                    time.sleep(0.1 * (2**attempt))
                    continue
                raise ScmUpstreamError(f"GitHub server error ({resp.status_code})")

            body = resp.json()
            if "etag" in resp_headers:
                self._etag_cache[cache_key] = (resp_headers["etag"], body, resp_headers)
            return body, resp_headers

        raise ScmUpstreamError("GitHub request failed") from last_exc

    def test_connection(self) -> ScmConnectionCheck:
        try:
            body, headers = self._get("/rate_limit")
        except ScmProviderError as exc:
            return ScmConnectionCheck(ok=False, mode=self.mode, diagnostics=str(exc))

        remaining = None
        if isinstance(body, dict):
            core = (body.get("resources") or {}).get("core") or {}
            if "remaining" in core:
                remaining = int(core["remaining"])

        if self._auth_type is ScmAuthType.GITHUB_APP:
            perms = self._installation_permissions
        else:
            scopes = headers.get("x-oauth-scopes", "")
            perms = {"oauth_scopes": scopes or "fine-grained-pat"}

        return ScmConnectionCheck(
            ok=True,
            mode=self.mode,
            permission_summary=perms,
            rate_limit_remaining=remaining,
            diagnostics="Connected to GitHub REST API (read-only).",
        )

    def get_repository(self, owner: str, repo: str) -> ScmRepository:
        body, _ = self._get(f"/repos/{owner}/{repo}")
        return ScmRepository(
            full_name=str(body["full_name"]),
            default_branch=str(body.get("default_branch", "main")),
            html_url=str(body["html_url"]),
            private=bool(body.get("private", False)),
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
        body, headers = self._get(
            f"/repos/{owner}/{repo}/commits",
            params={
                "since": since.astimezone(UTC).isoformat(),
                "until": until.astimezone(UTC).isoformat(),
                "page": page,
                "per_page": per_page,
            },
        )
        items = [
            ScmCommit(
                sha=str(row["sha"]),
                message=str((row.get("commit") or {}).get("message", "")).splitlines()[0][:200],
                author=str(
                    ((row.get("commit") or {}).get("author") or {}).get("name")
                    or (row.get("author") or {}).get("login")
                    or "unknown"
                ),
                committed_at=_parse_iso(
                    ((row.get("commit") or {}).get("author") or {}).get("date")
                ),
                html_url=str(row["html_url"]),
                repository=f"{owner}/{repo}",
            )
            for row in body
        ]
        return ScmPage(
            items=items, page=page, per_page=per_page, has_next=_has_next_page(headers.get("link"))
        )

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
        body, headers = self._get(
            f"/repos/{owner}/{repo}/pulls",
            params={
                "state": "all",
                "sort": "updated",
                "direction": "desc",
                "page": page,
                "per_page": per_page,
            },
        )
        items: list[ScmPullRequest] = []
        for row in body:
            created = _parse_iso(row.get("created_at"))
            merged = _parse_iso(row["merged_at"]) if row.get("merged_at") else None
            relevant_ts = merged or created
            if not (since.astimezone(UTC) <= relevant_ts <= until.astimezone(UTC)):
                continue
            reviews_body, _ = self._get(f"/repos/{owner}/{repo}/pulls/{row['number']}/reviews")
            reviews = [
                ScmReview(
                    author=str((r.get("user") or {}).get("login") or "unknown"),
                    state=str(r.get("state", "COMMENTED")),
                    submitted_at=_parse_iso(r["submitted_at"]) if r.get("submitted_at") else None,
                )
                for r in reviews_body
            ]
            items.append(
                ScmPullRequest(
                    number=int(row["number"]),
                    title=str(row["title"]),
                    state=str(row["state"]),
                    author=str((row.get("user") or {}).get("login") or "unknown"),
                    created_at=created,
                    merged_at=merged,
                    html_url=str(row["html_url"]),
                    repository=f"{owner}/{repo}",
                    reviews=reviews,
                )
            )
        return ScmPage(
            items=items, page=page, per_page=per_page, has_next=_has_next_page(headers.get("link"))
        )

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
        body, headers = self._get(
            f"/repos/{owner}/{repo}/deployments",
            params={"page": page, "per_page": per_page},
        )
        items: list[ScmDeployment] = []
        for row in body:
            created = _parse_iso(row.get("created_at"))
            if not (since.astimezone(UTC) <= created <= until.astimezone(UTC)):
                continue
            items.append(
                ScmDeployment(
                    id=int(row["id"]),
                    environment=str(row.get("environment", "production")),
                    state="recorded",
                    creator=str((row.get("creator") or {}).get("login") or "unknown"),
                    ref=str(row.get("ref", "main")),
                    created_at=created,
                    html_url=f"https://github.com/{owner}/{repo}/deployments",
                    repository=f"{owner}/{repo}",
                )
            )
        return ScmPage(
            items=items, page=page, per_page=per_page, has_next=_has_next_page(headers.get("link"))
        )
