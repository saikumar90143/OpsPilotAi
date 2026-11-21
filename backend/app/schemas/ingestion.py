"""Pydantic v2 schemas for integration configs, webhook receipts, simulator, and replay."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.integrations.base import AlertEventStatus
from app.models.inbound_event import InboundEventStatus
from app.models.integration import (
    INTEGRATION_NAME_MAX_LENGTH,
    ConnectionStatus,
    IntegrationProvider,
)


class IntegrationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: IntegrationProvider = IntegrationProvider.ALERTMANAGER
    name: str = Field(min_length=2, max_length=INTEGRATION_NAME_MAX_LENGTH)
    is_simulator_mode: bool = True


class IntegrationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=INTEGRATION_NAME_MAX_LENGTH)
    is_enabled: bool | None = None
    is_simulator_mode: bool | None = None


class IntegrationRead(BaseModel):
    """Public integration view — never exposes encrypted or plaintext secrets."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    provider: IntegrationProvider
    name: str
    is_enabled: bool
    is_simulator_mode: bool
    connection_status: ConnectionStatus
    webhook_path: str
    secret_rotated_at: datetime | None
    rotation_grace_until: datetime | None
    created_at: datetime
    updated_at: datetime


class IntegrationCreatedRead(IntegrationRead):
    """Returned once at creation time so the admin can configure the external sender."""

    signing_secret: str


class SecretRotatedRead(BaseModel):
    integration_id: int
    signing_secret: str
    rotation_grace_until: datetime


class SimulateWebhookRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: Literal["high_error_rate", "queue_backlog"] = "high_error_rate"
    status: AlertEventStatus = AlertEventStatus.FIRING


class WebhookReceiptResponse(BaseModel):
    accepted: bool
    duplicate: bool
    event_ids: list[int]
    status: str


class InboundEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    integration_id: int
    provider: str
    idempotency_key: str
    provider_event_id: str
    fingerprint: str
    is_simulated: bool
    status: InboundEventStatus
    attempt_count: int
    max_attempts: int
    last_error: str | None
    correlation_id: str
    incident_id: int | None
    normalized_payload_json: dict[str, Any]
    received_at: datetime
    processed_at: datetime | None
    next_retry_at: datetime | None
    dead_lettered_at: datetime | None
    updated_at: datetime
