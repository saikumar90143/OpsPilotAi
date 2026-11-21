"""Event ingestion, integration config, deduplication, retry/dead-letter, and simulator."""

import random
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import ConflictError, NotFoundError
from app.core.logging import NO_REQUEST_ID, redact, request_id_var
from app.core.secrets import decrypt_secret, encrypt_secret, verify_webhook_credentials
from app.core.security import generate_opaque_token
from app.core.telemetry import (
    QUEUE_DEAD_LETTERS_TOTAL,
    QUEUE_JOB_AGE_SECONDS,
    QUEUE_RETRIES_TOTAL,
    WEBHOOK_EVENTS_TOTAL,
)
from app.integrations.alertmanager import (
    PROVIDER_NAME as ALERTMANAGER_PROVIDER,
)
from app.integrations.alertmanager import (
    AdapterValidationError,
    build_sample_alertmanager_payload,
    parse_alertmanager_payload,
)
from app.integrations.base import AlertEventStatus, NormalizedAlertEvent
from app.models.inbound_event import InboundEvent, InboundEventStatus
from app.models.incident import Incident, IncidentStatus
from app.models.incident_details import IncidentAffectedService, IncidentTimelineEvent
from app.models.integration import ConnectionStatus, IntegrationConfig, IntegrationProvider
from app.repositories import audit_repo
from app.schemas.ingestion import (
    IntegrationCreate,
    IntegrationRead,
    IntegrationUpdate,
    SimulateWebhookRequest,
    WebhookReceiptResponse,
)

INTEGRATION_NOT_FOUND = "Integration not found"
EVENT_NOT_FOUND = "Inbound event not found"
SIMULATOR_SOURCE = "alertmanager-simulator"
LIVE_SOURCE = "alertmanager"
MAX_BACKOFF_SECONDS = 60

EnqueueFn = Callable[[int, str], None]


class PoisonEventError(ValueError):
    """Unrecoverable payload/schema error that should go straight to dead_letter."""


@dataclass(frozen=True)
class ProcessingOutcome:
    status: InboundEventStatus
    retry_countdown_seconds: int | None = None
    max_attempts: int = 3
    error_message: str | None = None


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def connection_status_for(config: IntegrationConfig) -> ConnectionStatus:
    if not config.is_enabled:
        return ConnectionStatus.DISABLED
    if config.is_simulator_mode:
        return ConnectionStatus.SIMULATOR
    return ConnectionStatus.CONFIGURED


def to_integration_read(config: IntegrationConfig) -> IntegrationRead:
    return IntegrationRead(
        id=config.id,
        organization_id=config.organization_id,
        provider=IntegrationProvider(config.provider),
        name=config.name,
        is_enabled=config.is_enabled,
        is_simulator_mode=config.is_simulator_mode,
        connection_status=connection_status_for(config),
        webhook_path=f"/api/v1/webhooks/{config.provider}/{config.webhook_endpoint_token}",
        secret_rotated_at=config.secret_rotated_at,
        rotation_grace_until=config.rotation_grace_until,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def create_integration(
    db: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    data: IntegrationCreate,
    settings: Settings,
    ip_address: str | None = None,
) -> tuple[IntegrationConfig, str]:
    raw_secret = generate_opaque_token()
    endpoint_token = secrets.token_urlsafe(18)
    config = IntegrationConfig(
        organization_id=organization_id,
        provider=data.provider.value,
        name=data.name.strip(),
        is_enabled=True,
        is_simulator_mode=data.is_simulator_mode,
        webhook_endpoint_token=endpoint_token,
        encrypted_signing_secret=encrypt_secret(raw_secret, settings),
    )
    db.add(config)
    db.flush()
    audit_repo.append_event(
        db,
        action="integration.created",
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        target_type="integration",
        target_id=config.id,
        ip_address=ip_address,
        metadata={"provider": config.provider, "is_simulator_mode": config.is_simulator_mode},
    )
    db.commit()
    db.refresh(config)
    return config, raw_secret


def list_integrations(db: Session, *, organization_id: int) -> list[IntegrationConfig]:
    stmt = (
        select(IntegrationConfig)
        .where(IntegrationConfig.organization_id == organization_id)
        .order_by(IntegrationConfig.id.asc())
    )
    return list(db.scalars(stmt).all())


def get_integration(db: Session, *, organization_id: int, integration_id: int) -> IntegrationConfig:
    config = db.scalar(
        select(IntegrationConfig).where(
            IntegrationConfig.id == integration_id,
            IntegrationConfig.organization_id == organization_id,
        )
    )
    if config is None:
        raise NotFoundError(INTEGRATION_NOT_FOUND)
    return config


def update_integration(
    db: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    integration_id: int,
    data: IntegrationUpdate,
    ip_address: str | None = None,
) -> IntegrationConfig:
    config = get_integration(db, organization_id=organization_id, integration_id=integration_id)
    if data.name is not None:
        config.name = data.name.strip()
    if data.is_enabled is not None:
        config.is_enabled = data.is_enabled
    if data.is_simulator_mode is not None:
        config.is_simulator_mode = data.is_simulator_mode
    audit_repo.append_event(
        db,
        action="integration.updated",
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        target_type="integration",
        target_id=config.id,
        ip_address=ip_address,
        metadata={"is_enabled": config.is_enabled, "is_simulator_mode": config.is_simulator_mode},
    )
    db.commit()
    db.refresh(config)
    return config


def rotate_integration_secret(
    db: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    integration_id: int,
    settings: Settings,
    ip_address: str | None = None,
) -> tuple[IntegrationConfig, str, datetime]:
    config = get_integration(db, organization_id=organization_id, integration_id=integration_id)
    now = datetime.now(UTC)
    grace_until = now + timedelta(hours=settings.secret_rotation_grace_hours)
    new_secret = generate_opaque_token()

    config.previous_encrypted_signing_secret = config.encrypted_signing_secret
    config.encrypted_signing_secret = encrypt_secret(new_secret, settings)
    config.secret_rotated_at = now
    config.rotation_grace_until = grace_until

    audit_repo.append_event(
        db,
        action="integration.secret_rotated",
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        target_type="integration",
        target_id=config.id,
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(config)
    return config, new_secret, grace_until


def get_enabled_integration_by_token(
    db: Session, *, provider: str, endpoint_token: str
) -> IntegrationConfig:
    config = db.scalar(
        select(IntegrationConfig).where(
            IntegrationConfig.provider == provider,
            IntegrationConfig.webhook_endpoint_token == endpoint_token,
            IntegrationConfig.is_enabled.is_(True),
        )
    )
    if config is None:
        raise NotFoundError(INTEGRATION_NOT_FOUND)
    return config


def _candidate_secrets(config: IntegrationConfig, settings: Settings) -> list[str]:
    secrets_list = [decrypt_secret(config.encrypted_signing_secret, settings)]
    if (
        config.previous_encrypted_signing_secret
        and config.rotation_grace_until is not None
        and _as_utc(config.rotation_grace_until) >= datetime.now(UTC)
    ):
        secrets_list.append(decrypt_secret(config.previous_encrypted_signing_secret, settings))
    return secrets_list


def receive_alertmanager_webhook(
    db: Session,
    *,
    endpoint_token: str,
    raw_body: bytes,
    raw_payload: dict[str, Any],
    signature_header: str | None,
    authorization_header: str | None,
    settings: Settings,
    enqueue_fn: EnqueueFn,
    ip_address: str | None = None,
) -> WebhookReceiptResponse:
    config = get_enabled_integration_by_token(
        db, provider=ALERTMANAGER_PROVIDER, endpoint_token=endpoint_token
    )
    verify_webhook_credentials(
        raw_body=raw_body,
        signature_header=signature_header,
        authorization_header=authorization_header,
        candidate_secrets=_candidate_secrets(config, settings),
        tolerance_seconds=settings.webhook_signature_tolerance_seconds,
    )
    return _persist_and_enqueue(
        db,
        config=config,
        raw_payload=raw_payload,
        is_simulated=config.is_simulator_mode,
        settings=settings,
        enqueue_fn=enqueue_fn,
        ip_address=ip_address,
    )


def simulate_alertmanager_webhook(
    db: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    integration_id: int,
    request_data: SimulateWebhookRequest,
    settings: Settings,
    enqueue_fn: EnqueueFn,
    ip_address: str | None = None,
) -> WebhookReceiptResponse:
    config = get_integration(db, organization_id=organization_id, integration_id=integration_id)
    if not config.is_enabled:
        raise ConflictError("Integration is disabled")

    payload = build_sample_alertmanager_payload(
        scenario=request_data.scenario, status=request_data.status
    )
    audit_repo.append_event(
        db,
        action="integration.simulated",
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        target_type="integration",
        target_id=config.id,
        ip_address=ip_address,
        metadata={"scenario": request_data.scenario, "status": request_data.status.value},
    )
    return _persist_and_enqueue(
        db,
        config=config,
        raw_payload=payload,
        is_simulated=True,
        settings=settings,
        enqueue_fn=enqueue_fn,
        ip_address=ip_address,
    )


def _persist_and_enqueue(
    db: Session,
    *,
    config: IntegrationConfig,
    raw_payload: dict[str, Any],
    is_simulated: bool,
    settings: Settings,
    enqueue_fn: EnqueueFn,
    ip_address: str | None = None,
) -> WebhookReceiptResponse:
    try:
        normalized_events = parse_alertmanager_payload(raw_payload, is_simulated=is_simulated)
    except AdapterValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    correlation_id = request_id_var.get() or NO_REQUEST_ID
    new_events: list[InboundEvent] = []
    all_event_ids: list[int] = []
    any_duplicate = False

    for norm in normalized_events:
        existing = db.scalar(
            select(InboundEvent).where(
                InboundEvent.organization_id == config.organization_id,
                InboundEvent.provider == norm.provider,
                InboundEvent.idempotency_key == norm.idempotency_key,
            )
        )
        if existing is not None:
            any_duplicate = True
            all_event_ids.append(existing.id)
            continue

        row = InboundEvent(
            organization_id=config.organization_id,
            integration_id=config.id,
            provider=norm.provider,
            idempotency_key=norm.idempotency_key,
            provider_event_id=norm.provider_event_id,
            fingerprint=norm.fingerprint,
            is_simulated=norm.is_simulated,
            status=InboundEventStatus.RECEIVED.value,
            attempt_count=0,
            max_attempts=settings.event_max_attempts,
            correlation_id=correlation_id,
            raw_payload_json=audit_repo.sanitize_metadata(raw_payload),
            normalized_payload_json=norm.model_dump(mode="json"),
        )
        db.add(row)
        db.flush()
        new_events.append(row)
        all_event_ids.append(row.id)

    if new_events:
        audit_repo.append_event(
            db,
            action="event.received",
            organization_id=config.organization_id,
            target_type="integration",
            target_id=config.id,
            ip_address=ip_address,
            metadata={"count": len(new_events), "is_simulated": is_simulated},
        )
    # Persist receipt before enqueueing so queue failure never loses the event.
    db.commit()

    if not new_events:
        WEBHOOK_EVENTS_TOTAL.labels(provider=config.provider, outcome="duplicate").inc()
        return WebhookReceiptResponse(
            accepted=True,
            duplicate=any_duplicate,
            event_ids=all_event_ids,
            status="duplicate",
        )

    for row in new_events:
        try:
            enqueue_fn(row.id, correlation_id)
        except Exception as exc:
            row.last_error = redact(str(exc))[:500]
            db.commit()
            raise
        row.status = InboundEventStatus.QUEUED.value
    db.commit()
    WEBHOOK_EVENTS_TOTAL.labels(provider=config.provider, outcome="accepted").inc(len(new_events))

    return WebhookReceiptResponse(
        accepted=True,
        duplicate=any_duplicate,
        event_ids=all_event_ids,
        status=InboundEventStatus.QUEUED.value,
    )


def _find_active_incident_by_fingerprint(
    db: Session, *, organization_id: int, fingerprint: str
) -> Incident | None:
    return db.scalar(
        select(Incident)
        .where(
            Incident.organization_id == organization_id,
            Incident.fingerprint == fingerprint,
            Incident.archived_at.is_(None),
            Incident.status != IncidentStatus.CLOSED.value,
        )
        .order_by(Incident.created_at.desc(), Incident.id.desc())
    )


def apply_normalized_event(db: Session, *, event: InboundEvent) -> Incident | None:
    """Create, deduplicate, or resolve an Incident from a persisted InboundEvent."""
    try:
        norm = NormalizedAlertEvent.model_validate(event.normalized_payload_json)
    except ValidationError as exc:
        raise PoisonEventError(f"Malformed normalized payload: {exc.errors()[0]['msg']}") from exc

    active = _find_active_incident_by_fingerprint(
        db, organization_id=event.organization_id, fingerprint=norm.fingerprint
    )
    source_name = SIMULATOR_SOURCE if norm.is_simulated else LIVE_SOURCE
    event_metadata = audit_repo.sanitize_metadata(
        {"simulated": norm.is_simulated, "labels": norm.labels, "provider": norm.provider}
    )

    if norm.event_status is AlertEventStatus.FIRING:
        if active is None:
            incident = Incident(
                organization_id=event.organization_id,
                title=norm.title,
                description=norm.description,
                service=norm.service,
                environment=norm.environment.value,
                severity=norm.severity.value,
                status=IncidentStatus.OPEN.value,
                source=source_name,
                external_source_id=norm.provider_event_id,
                fingerprint=norm.fingerprint,
                metadata_json=event_metadata,
            )
            db.add(incident)
            db.flush()
            db.add(
                IncidentAffectedService(
                    organization_id=event.organization_id,
                    incident_id=incident.id,
                    service_name=norm.service,
                )
            )
            db.add(
                IncidentTimelineEvent(
                    organization_id=event.organization_id,
                    incident_id=incident.id,
                    actor_user_id=None,
                    event_type="incident.created_from_event",
                    message=f"Incident opened from {source_name} alert ({norm.severity.value})",
                    details_json={
                        "inbound_event_id": event.id,
                        "is_simulated": norm.is_simulated,
                    },
                )
            )
            audit_repo.append_event(
                db,
                action="incident.created_from_event",
                organization_id=event.organization_id,
                target_type="incident",
                target_id=incident.id,
                metadata={"inbound_event_id": event.id, "is_simulated": norm.is_simulated},
            )
            event.incident_id = incident.id
            return incident

        # Deduplicated onto existing active incident without duplicating timeline for same event.
        if event.incident_id is None:
            event.incident_id = active.id
            db.add(
                IncidentTimelineEvent(
                    organization_id=event.organization_id,
                    incident_id=active.id,
                    actor_user_id=None,
                    event_type="incident.alert_deduplicated",
                    message=f"Deduplicated {source_name} firing alert",
                    details_json={
                        "inbound_event_id": event.id,
                        "is_simulated": norm.is_simulated,
                    },
                )
            )
        return active

    # AlertEventStatus.RESOLVED
    if active is None:
        return None

    event.incident_id = active.id
    if active.status != IncidentStatus.RESOLVED.value:
        previous_status = active.status
        active.status = IncidentStatus.RESOLVED.value
        active.resolved_at = _as_utc(norm.occurred_at)
        active.version += 1
        db.add(
            IncidentTimelineEvent(
                organization_id=event.organization_id,
                incident_id=active.id,
                actor_user_id=None,
                event_type="incident.resolved_by_event",
                message=f"Resolved by {source_name} recovery event",
                details_json={
                    "inbound_event_id": event.id,
                    "from": previous_status,
                    "is_simulated": norm.is_simulated,
                },
            )
        )
        audit_repo.append_event(
            db,
            action="incident.resolved_by_event",
            organization_id=event.organization_id,
            target_type="incident",
            target_id=active.id,
            metadata={"inbound_event_id": event.id, "is_simulated": norm.is_simulated},
        )
    return active


def execute_event_processing(
    db: Session,
    *,
    event_id: int,
    processor_fn: Callable[[Session, InboundEvent], Incident | None] | None = None,
) -> ProcessingOutcome:
    """Process one InboundEvent with bounded exponential backoff + jitter and dead-lettering."""
    event = db.get(InboundEvent, event_id)
    if event is None:
        return ProcessingOutcome(
            status=InboundEventStatus.DEAD_LETTER, error_message="Missing event"
        )
    if event.status == InboundEventStatus.PROCESSED.value:
        return ProcessingOutcome(status=InboundEventStatus.PROCESSED)

    event.status = InboundEventStatus.PROCESSING.value
    event.attempt_count += 1
    db.flush()

    fn = processor_fn or (lambda s, ev: apply_normalized_event(s, event=ev))
    try:
        fn(db, event)
    except PoisonEventError as exc:
        return _mark_dead_letter(db, event=event, error=str(exc))
    except Exception as exc:
        if event.attempt_count >= event.max_attempts:
            return _mark_dead_letter(db, event=event, error=str(exc))

        countdown = min(
            MAX_BACKOFF_SECONDS, int((2**event.attempt_count) + random.uniform(0.0, 1.0))
        )
        now = datetime.now(UTC)
        event.status = InboundEventStatus.RETRYING.value
        event.next_retry_at = now + timedelta(seconds=countdown)
        event.last_error = redact(str(exc))[:500]
        db.commit()
        QUEUE_RETRIES_TOTAL.labels(provider=event.provider).inc()
        return ProcessingOutcome(
            status=InboundEventStatus.RETRYING,
            retry_countdown_seconds=countdown,
            max_attempts=event.max_attempts,
            error_message=event.last_error,
        )

    event.status = InboundEventStatus.PROCESSED.value
    event.processed_at = datetime.now(UTC)
    event.next_retry_at = None
    event.last_error = None
    created_utc = (
        event.received_at.replace(tzinfo=UTC)
        if event.received_at.tzinfo is None
        else event.received_at.astimezone(UTC)
    )
    QUEUE_JOB_AGE_SECONDS.labels(status="processed").observe(
        max(0.0, (event.processed_at - created_utc).total_seconds())
    )
    db.commit()
    QUEUE_DEAD_LETTERS_TOTAL.labels(provider=event.provider).inc()
    return ProcessingOutcome(status=InboundEventStatus.PROCESSED)


def _mark_dead_letter(db: Session, *, event: InboundEvent, error: str) -> ProcessingOutcome:
    now = datetime.now(UTC)
    sanitized_error = redact(error)[:500]
    event.status = InboundEventStatus.DEAD_LETTER.value
    event.dead_lettered_at = now
    event.next_retry_at = None
    event.last_error = sanitized_error
    audit_repo.append_event(
        db,
        action="event.dead_lettered",
        organization_id=event.organization_id,
        target_type="inbound_event",
        target_id=event.id,
        metadata={"attempts": event.attempt_count, "error": sanitized_error},
    )
    db.commit()
    QUEUE_DEAD_LETTERS_TOTAL.labels(provider=event.provider).inc()
    return ProcessingOutcome(
        status=InboundEventStatus.DEAD_LETTER,
        max_attempts=event.max_attempts,
        error_message=sanitized_error,
    )


def list_events(
    db: Session,
    *,
    organization_id: int,
    status_filter: InboundEventStatus | None = None,
    provider: str | None = None,
    is_simulated: bool | None = None,
    limit: int = 50,
) -> list[InboundEvent]:
    stmt = select(InboundEvent).where(InboundEvent.organization_id == organization_id)
    if status_filter is not None:
        stmt = stmt.where(InboundEvent.status == status_filter.value)
    if provider is not None:
        stmt = stmt.where(InboundEvent.provider == provider)
    if is_simulated is not None:
        stmt = stmt.where(InboundEvent.is_simulated.is_(is_simulated))
    stmt = stmt.order_by(InboundEvent.received_at.desc(), InboundEvent.id.desc()).limit(limit)
    return list(db.scalars(stmt).all())


def get_event(db: Session, *, organization_id: int, event_id: int) -> InboundEvent:
    event = db.scalar(
        select(InboundEvent).where(
            InboundEvent.id == event_id,
            InboundEvent.organization_id == organization_id,
        )
    )
    if event is None:
        raise NotFoundError(EVENT_NOT_FOUND)
    return event


def replay_event(
    db: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    event_id: int,
    enqueue_fn: EnqueueFn,
    ip_address: str | None = None,
) -> InboundEvent:
    event = get_event(db, organization_id=organization_id, event_id=event_id)
    correlation_id = request_id_var.get() or NO_REQUEST_ID

    event.status = InboundEventStatus.RECEIVED.value
    event.attempt_count = 0
    event.dead_lettered_at = None
    event.next_retry_at = None
    event.last_error = None
    event.correlation_id = correlation_id

    audit_repo.append_event(
        db,
        action="event.replayed",
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        target_type="inbound_event",
        target_id=event.id,
        ip_address=ip_address,
    )
    db.commit()

    try:
        enqueue_fn(event.id, correlation_id)
    except Exception as exc:
        event.last_error = redact(str(exc))[:500]
        db.commit()
        raise

    event.status = InboundEventStatus.QUEUED.value
    db.commit()
    db.refresh(event)
    return event


def default_settings() -> Settings:
    return get_settings()
