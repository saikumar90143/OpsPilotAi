"""Deterministic mock adapters for Jira and Slack external write actions."""

import hashlib
from typing import Any

from app.integrations.actions.base import (
    ActionConnectionTestResult,
    ActionExecutionResult,
    ActionPermissionError,
    ActionProviderError,
    ActionTimeoutError,
)


class MockJiraAdapter:
    """Deterministic local Jira adapter (no external network calls)."""

    def __init__(self, *, allowed_projects: list[str]) -> None:
        self._allowed_projects = allowed_projects

    def test_connection(self) -> ActionConnectionTestResult:
        return ActionConnectionTestResult(
            ok=True,
            mode="mock",
            permission_summary={
                "scope": "write:jira-work (simulated)",
                "allowed_projects": ", ".join(self._allowed_projects) or "none",
            },
            diagnostics="Mock Jira adapter healthy (no live Jira account connected).",
        )

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
        if payload.get("_simulate") == "permission_denied":
            raise ActionPermissionError("Simulated Jira 403 Forbidden: missing CREATE_ISSUES")
        if payload.get("_simulate") == "timeout":
            raise ActionTimeoutError("Simulated Jira request timeout")

        suffix = (
            int(hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:4], 16) % 900 + 100
        )
        key = f"MOCK-{destination}-{suffix}"
        return ActionExecutionResult(
            external_id=key,
            external_url=f"https://mock-jira.local/browse/{key}",
            response_summary={
                "issue_key": key,
                "project": destination,
                "summary": str(payload.get("summary", ""))[:120],
                "is_mock": True,
            },
            is_mock=True,
        )


class MockSlackAdapter:
    """Deterministic local Slack adapter (no external network calls)."""

    def __init__(self, *, allowed_channels: list[str]) -> None:
        self._allowed_channels = allowed_channels

    def test_connection(self) -> ActionConnectionTestResult:
        return ActionConnectionTestResult(
            ok=True,
            mode="mock",
            permission_summary={
                "scope": "chat:write (simulated)",
                "allowed_channels": ", ".join(self._allowed_channels) or "none",
            },
            diagnostics="Mock Slack adapter healthy (no live Slack workspace connected).",
        )

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
        if payload.get("_simulate") == "permission_denied":
            raise ActionPermissionError("Simulated Slack missing_scope: chat:write required")
        if payload.get("_simulate") == "timeout":
            raise ActionTimeoutError("Simulated Slack request timeout")

        ts_suffix = (
            int(hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:6], 16) % 999999
        )
        ts = f"1700000000.{ts_suffix:06d}"
        return ActionExecutionResult(
            external_id=ts,
            external_url=f"https://mock-slack.local/archives/{destination}/p{ts.replace('.', '')}",
            response_summary={
                "channel": destination,
                "ts": ts,
                "text_preview": str(payload.get("text", ""))[:120],
                "is_mock": True,
            },
            is_mock=True,
        )
