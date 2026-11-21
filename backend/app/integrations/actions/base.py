"""Provider-neutral interface and error hierarchy for external write actions."""

from dataclasses import dataclass
from typing import Any, Protocol


class ActionProviderError(Exception):
    """Base error for external action connectors (never contains secrets)."""


class ActionPermissionError(ActionProviderError):
    """Raised when the external connector lacks permission/scope (401/403)."""


class ActionTimeoutError(ActionProviderError):
    """Raised when an external provider request times out or hits transient 5xx."""


@dataclass(frozen=True)
class ActionConnectionTestResult:
    ok: bool
    mode: str
    permission_summary: dict[str, str]
    diagnostics: str


@dataclass(frozen=True)
class ActionExecutionResult:
    external_id: str
    external_url: str | None
    response_summary: dict[str, Any]
    is_mock: bool


class ActionProvider(Protocol):
    def test_connection(self) -> ActionConnectionTestResult: ...

    def execute_action(
        self,
        *,
        action_type: str,
        destination: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> ActionExecutionResult: ...
