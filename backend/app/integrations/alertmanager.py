"""Prometheus Alertmanager v4 webhook adapter and local deterministic sample payloads."""

import hashlib
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.integrations.base import AlertEventStatus, NormalizedAlertEvent
from app.models.incident import (
    SERVICE_MAX_LENGTH,
    TITLE_MAX_LENGTH,
    Environment,
    Severity,
)

PROVIDER_NAME = "alertmanager"

_SEVERITY_MAP: dict[str, Severity] = {
    "critical": Severity.CRITICAL,
    "page": Severity.CRITICAL,
    "high": Severity.HIGH,
    "error": Severity.HIGH,
    "warning": Severity.MEDIUM,
    "warn": Severity.MEDIUM,
    "medium": Severity.MEDIUM,
    "info": Severity.LOW,
    "low": Severity.LOW,
}

_ENVIRONMENT_MAP: dict[str, Environment] = {
    "prod": Environment.PRODUCTION,
    "production": Environment.PRODUCTION,
    "stage": Environment.STAGING,
    "staging": Environment.STAGING,
    "dev": Environment.DEVELOPMENT,
    "development": Environment.DEVELOPMENT,
}


class AlertmanagerAlert(BaseModel):
    status: AlertEventStatus
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    startsAt: datetime
    endsAt: datetime | None = None
    generatorURL: str | None = None
    fingerprint: str | None = None


class AlertmanagerWebhookPayload(BaseModel):
    version: str = "4"
    groupKey: str = Field(min_length=1, max_length=255)
    status: AlertEventStatus
    receiver: str = "opspilot"
    groupLabels: dict[str, str] = Field(default_factory=dict)
    commonLabels: dict[str, str] = Field(default_factory=dict)
    commonAnnotations: dict[str, str] = Field(default_factory=dict)
    externalURL: str | None = None
    alerts: list[AlertmanagerAlert] = Field(min_length=1, max_length=100)


class AdapterValidationError(ValueError):
    """Raised when an inbound provider payload fails schema or timestamp validation."""


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _deterministic_fingerprint(alert: AlertmanagerAlert, group_key: str) -> str:
    if alert.fingerprint and alert.fingerprint.strip():
        return alert.fingerprint.strip()[:128]
    raw = f"{group_key}:{sorted(alert.labels.items())}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def parse_alertmanager_payload(
    raw_payload: dict[str, Any], *, is_simulated: bool = False
) -> list[NormalizedAlertEvent]:
    """Validate and normalize an Alertmanager v4 webhook into canonical events."""
    try:
        parsed = AlertmanagerWebhookPayload.model_validate(raw_payload)
    except ValidationError as exc:
        raise AdapterValidationError(
            f"Invalid Alertmanager payload: {exc.errors()[0]['msg']}"
        ) from exc

    events: list[NormalizedAlertEvent] = []
    for alert in parsed.alerts:
        labels = {**parsed.commonLabels, **alert.labels}
        annotations = {**parsed.commonAnnotations, **alert.annotations}

        fingerprint = _deterministic_fingerprint(alert, parsed.groupKey)
        starts_utc = _as_utc(alert.startsAt)
        occurred_at = (
            _as_utc(alert.endsAt)
            if alert.status is AlertEventStatus.RESOLVED and alert.endsAt is not None
            else starts_utc
        )

        raw_severity = labels.get("severity", "medium").strip().lower()
        severity = _SEVERITY_MAP.get(raw_severity, Severity.MEDIUM)

        raw_env = (labels.get("environment") or labels.get("env") or "unknown").strip().lower()
        environment = _ENVIRONMENT_MAP.get(raw_env, Environment.UNKNOWN)

        service = (
            labels.get("service") or labels.get("app") or labels.get("job") or "unknown-service"
        ).strip()[:SERVICE_MAX_LENGTH]
        if len(service) < 2:
            service = "unknown-service"

        alert_name = labels.get("alertname", "AlertmanagerAlert").strip()
        summary = annotations.get("summary") or annotations.get("message") or alert_name
        title = summary[:TITLE_MAX_LENGTH]
        if len(title) < 4:
            title = f"Alert: {alert_name}"[:TITLE_MAX_LENGTH]
        description = annotations.get("description") or summary

        provider_event_id = f"{fingerprint}:{alert.status.value}:{int(starts_utc.timestamp())}"
        idempotency_key = f"{parsed.groupKey}:{provider_event_id}"[:255]

        events.append(
            NormalizedAlertEvent(
                provider=PROVIDER_NAME,
                provider_event_id=provider_event_id[:128],
                idempotency_key=idempotency_key,
                fingerprint=fingerprint,
                title=title,
                description=description,
                service=service,
                environment=environment,
                severity=severity,
                event_status=alert.status,
                occurred_at=occurred_at,
                is_simulated=is_simulated,
                labels=labels,
                annotations=annotations,
            )
        )
    return events


def build_sample_alertmanager_payload(
    *,
    scenario: str = "high_error_rate",
    status: AlertEventStatus = AlertEventStatus.FIRING,
) -> dict[str, Any]:
    """Deterministic local sample Alertmanager payload for simulator & tests."""
    starts_at = "2026-11-21T08:00:00Z"
    ends_at = (
        "2026-11-21T08:12:00Z" if status is AlertEventStatus.RESOLVED else "0001-01-01T00:00:00Z"
    )
    if scenario == "queue_backlog":
        alert_name = "WorkerQueueBacklog"
        service = "orders-worker"
        severity = "warning"
        summary = "Orders worker queue backlog above threshold"
        description = "Pending jobs exceeded 2,000 for 5 minutes."
        fingerprint = "sim-fp-orders-worker-backlog"
    else:
        alert_name = "CheckoutHighErrorRate"
        service = "checkout-api"
        severity = "critical"
        summary = "Checkout API HTTP 5xx error rate above 5%"
        description = "5xx error rate reached 8.7% on checkout-api in production."
        fingerprint = "sim-fp-checkout-5xx"

    return {
        "version": "4",
        "groupKey": f"sim:{scenario}",
        "status": status.value,
        "receiver": "opspilot-simulator",
        "groupLabels": {"alertname": alert_name},
        "commonLabels": {
            "alertname": alert_name,
            "service": service,
            "environment": "production",
            "severity": severity,
        },
        "commonAnnotations": {
            "summary": summary,
            "description": description,
        },
        "alerts": [
            {
                "status": status.value,
                "labels": {
                    "alertname": alert_name,
                    "service": service,
                    "environment": "production",
                    "severity": severity,
                },
                "annotations": {
                    "summary": summary,
                    "description": description,
                },
                "startsAt": starts_at,
                "endsAt": ends_at,
                "fingerprint": fingerprint,
            }
        ],
    }
