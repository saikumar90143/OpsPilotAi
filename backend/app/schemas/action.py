"""Pydantic v2 schemas for external action connectors and human-gated ProposedAction."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.ssrf import validate_safe_outbound_url
from app.models.action import ActionConnectorMode, ActionProviderType, ActionType


class ActionConnectorCreate(BaseModel):
    provider: ActionProviderType
    name: str = Field(min_length=2, max_length=100)
    mode: ActionConnectorMode = ActionConnectorMode.MOCK
    base_url: str | None = Field(default=None, max_length=300)
    allowed_targets: list[str] = Field(min_length=1, max_length=50)
    credential: str | None = Field(default=None, max_length=2000)

    @field_validator("base_url")
    @classmethod
    def _validate_https(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return validate_safe_outbound_url(value)

    @field_validator("allowed_targets")
    @classmethod
    def _clean_targets(cls, values: list[str]) -> list[str]:
        cleaned = [v.strip() for v in values if v.strip()]
        if not cleaned:
            raise ValueError("At least one allowlisted target project or channel is required")
        return list(dict.fromkeys(cleaned))


class ActionConnectorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    provider: str
    name: str
    mode: str
    base_url: str | None
    allowed_targets_json: list[str]
    has_credential: bool = False
    permission_summary_json: dict[str, str]
    last_test_status: str
    last_test_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class ActionConnectorTestOut(BaseModel):
    ok: bool
    mode: str
    permission_summary: dict[str, str]
    diagnostics: str


class JiraIssuePayload(BaseModel):
    summary: str = Field(min_length=4, max_length=200)
    description: str = Field(min_length=4, max_length=4000)
    issue_type: str = Field(default="Incident", min_length=2, max_length=40)
    labels: list[str] = Field(default_factory=list, max_length=10)


class SlackMessagePayload(BaseModel):
    text: str = Field(min_length=4, max_length=3000)


class ProposedActionCreate(BaseModel):
    connector_id: int
    investigation_id: int | None = None
    action_type: ActionType
    target_destination: str = Field(min_length=2, max_length=120)
    payload: dict[str, Any]
    evidence_links: list[str] = Field(default_factory=list, max_length=20)
    requested_by_type: Literal["user", "ai"] = "user"
    idempotency_key: str | None = Field(default=None, min_length=4, max_length=128)
    ttl_hours: int | None = Field(default=None, ge=1, le=168)


class ProposedActionRejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class ProposedActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    incident_id: int
    investigation_id: int | None
    connector_id: int
    connector_mode: str = "mock"
    action_type: str
    target_system: str
    target_destination: str
    payload_preview_json: dict[str, Any]
    payload_hash: str
    evidence_links_json: list[str]
    requested_by_type: str
    requested_by_user_id: int | None
    status: str
    approved_by_user_id: int | None
    approved_at: datetime | None
    rejected_by_user_id: int | None
    rejected_at: datetime | None
    rejection_reason: str | None
    expires_at: datetime
    idempotency_key: str
    execution_attempts: int
    external_id: str | None
    external_url: str | None
    execution_result_json: dict[str, Any] | None
    last_error: str | None
    executed_at: datetime | None
    audit_metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime
