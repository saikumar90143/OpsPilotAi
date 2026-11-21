"""Live Jira & Slack clients with narrow scopes, timeouts, and redacted diagnostics."""

from typing import Any

import httpx2

from app.core.redaction import redact_text
from app.integrations.actions.base import (
    ActionConnectionTestResult,
    ActionExecutionResult,
    ActionPermissionError,
    ActionProviderError,
    ActionTimeoutError,
)


class LiveJiraClient:
    """Narrow-scope Jira Cloud REST v3 client (requires explicit credentials)."""

    def __init__(self, *, base_url: str, credential: str, timeout_seconds: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._credential = credential
        self._timeout = timeout_seconds

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._credential}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def test_connection(self) -> ActionConnectionTestResult:
        try:
            with httpx2.Client(timeout=self._timeout) as client:
                resp = client.get(f"{self._base_url}/rest/api/3/myself", headers=self._headers())
            if resp.status_code in (401, 403):
                raise ActionPermissionError(f"Jira auth/permission failed ({resp.status_code})")
            if resp.status_code >= 400:
                raise ActionProviderError(f"Jira returned HTTP {resp.status_code}")
            return ActionConnectionTestResult(
                ok=True,
                mode="live",
                permission_summary={"scope": "write:jira-work", "endpoint": self._base_url},
                diagnostics="Live Jira connection verified.",
            )
        except httpx2.TimeoutException as exc:
            raise ActionTimeoutError("Jira connection test timed out") from exc
        except httpx2.HTTPError as exc:
            raise ActionProviderError(redact_text(f"Jira transport error: {exc}")) from exc

    def execute_action(
        self,
        *,
        action_type: str,
        destination: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> ActionExecutionResult:
        if action_type != "jira_create_issue":
            raise ActionProviderError(f"Unsupported Jira action_type: {action_type}")
        body = {
            "fields": {
                "project": {"key": destination},
                "summary": payload["summary"],
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": payload["description"]}],
                        }
                    ],
                },
                "issuetype": {"name": payload.get("issue_type", "Incident")},
                "labels": payload.get("labels", []),
            }
        }
        try:
            with httpx2.Client(timeout=self._timeout) as client:
                resp = client.post(
                    f"{self._base_url}/rest/api/3/issue",
                    headers={**self._headers(), "Idempotency-Key": idempotency_key},
                    json=body,
                )
            if resp.status_code in (401, 403):
                raise ActionPermissionError(f"Jira permission denied ({resp.status_code})")
            if resp.status_code >= 500:
                raise ActionTimeoutError(f"Jira server error ({resp.status_code})")
            if resp.status_code >= 400:
                raise ActionProviderError(f"Jira rejected request ({resp.status_code})")
            data = resp.json()
            key = str(data.get("key", ""))
            return ActionExecutionResult(
                external_id=key,
                external_url=f"{self._base_url}/browse/{key}" if key else None,
                response_summary={"issue_key": key, "project": destination, "is_mock": False},
                is_mock=False,
            )
        except httpx2.TimeoutException as exc:
            raise ActionTimeoutError("Jira create issue timed out") from exc
        except httpx2.HTTPError as exc:
            raise ActionProviderError(redact_text(f"Jira request error: {exc}")) from exc


class LiveSlackClient:
    """Narrow-scope Slack Web API client (chat:write)."""

    def __init__(self, *, credential: str, timeout_seconds: float = 10.0) -> None:
        self._base_url = "https://slack.com/api"
        self._credential = credential
        self._timeout = timeout_seconds

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._credential}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def test_connection(self) -> ActionConnectionTestResult:
        try:
            with httpx2.Client(timeout=self._timeout) as client:
                resp = client.post(f"{self._base_url}/auth.test", headers=self._headers())
            data = resp.json()
            if not data.get("ok"):
                err = str(data.get("error", "unknown_error"))
                if err in ("invalid_auth", "not_authed", "missing_scope"):
                    raise ActionPermissionError(f"Slack auth failed: {err}")
                raise ActionProviderError(f"Slack error: {err}")
            return ActionConnectionTestResult(
                ok=True,
                mode="live",
                permission_summary={
                    "scope": "chat:write",
                    "team": str(data.get("team", "unknown")),
                },
                diagnostics="Live Slack bot token verified.",
            )
        except httpx2.TimeoutException as exc:
            raise ActionTimeoutError("Slack auth.test timed out") from exc
        except httpx2.HTTPError as exc:
            raise ActionProviderError(redact_text(f"Slack transport error: {exc}")) from exc

    def execute_action(
        self,
        *,
        action_type: str,
        destination: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> ActionExecutionResult:
        if action_type != "slack_post_message":
            raise ActionProviderError(f"Unsupported Slack action_type: {action_type}")
        try:
            with httpx2.Client(timeout=self._timeout) as client:
                resp = client.post(
                    f"{self._base_url}/chat.postMessage",
                    headers={**self._headers(), "X-Idempotency-Key": idempotency_key},
                    json={"channel": destination, "text": payload["text"]},
                )
            if resp.status_code >= 500:
                raise ActionTimeoutError(f"Slack server error ({resp.status_code})")
            data = resp.json()
            if not data.get("ok"):
                err = str(data.get("error", "unknown_error"))
                if err in ("invalid_auth", "not_authed", "missing_scope", "channel_not_found"):
                    raise ActionPermissionError(f"Slack permission/channel error: {err}")
                raise ActionProviderError(f"Slack API error: {err}")
            ts = str(data.get("ts", ""))
            return ActionExecutionResult(
                external_id=ts,
                external_url=None,
                response_summary={"channel": destination, "ts": ts, "is_mock": False},
                is_mock=False,
            )
        except httpx2.TimeoutException as exc:
            raise ActionTimeoutError("Slack postMessage timed out") from exc
        except httpx2.HTTPError as exc:
            raise ActionProviderError(redact_text(f"Slack request error: {exc}")) from exc
