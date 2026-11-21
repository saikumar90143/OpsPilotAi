"""Provider-neutral normalized alert event contract."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.models.incident import Environment, Severity


class AlertEventStatus(StrEnum):
    FIRING = "firing"
    RESOLVED = "resolved"


class NormalizedAlertEvent(BaseModel):
    """Canonical alert event produced by every provider adapter."""

    provider: str
    provider_event_id: str
    idempotency_key: str
    fingerprint: str
    title: str
    description: str
    service: str
    environment: Environment
    severity: Severity
    event_status: AlertEventStatus
    occurred_at: datetime
    is_simulated: bool = False
    labels: dict[str, Any] = Field(default_factory=dict)
    annotations: dict[str, Any] = Field(default_factory=dict)
