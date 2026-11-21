"""Integration management, secret rotation, webhook simulator, and event replay endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import AppSettings, DbSession, get_client_ip, require_permission
from app.api.errors import ERROR_RESPONSES
from app.api.v1.webhooks import get_enqueue_fn
from app.core.permissions import Permission
from app.models.inbound_event import InboundEvent, InboundEventStatus
from app.schemas.ingestion import (
    InboundEventRead,
    IntegrationCreate,
    IntegrationCreatedRead,
    IntegrationRead,
    IntegrationUpdate,
    SecretRotatedRead,
    SimulateWebhookRequest,
    WebhookReceiptResponse,
)
from app.services import ingestion_service
from app.services.auth_service import AuthContext
from app.services.ingestion_service import EnqueueFn

router = APIRouter(responses=ERROR_RESPONSES)


@router.post(
    "/integrations",
    response_model=IntegrationCreatedRead,
    status_code=status.HTTP_201_CREATED,
    tags=["integrations"],
)
def create_integration(
    payload: IntegrationCreate,
    request: Request,
    db: DbSession,
    settings: AppSettings,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INTEGRATION_MANAGE))],
) -> IntegrationCreatedRead:
    """Create a tenant-scoped integration and return its signing secret once."""
    config, raw_secret = ingestion_service.create_integration(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        data=payload,
        settings=settings,
        ip_address=get_client_ip(request),
    )
    base = ingestion_service.to_integration_read(config)
    return IntegrationCreatedRead(**base.model_dump(), signing_secret=raw_secret)


@router.get("/integrations", response_model=list[IntegrationRead], tags=["integrations"])
def list_integrations(
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INTEGRATION_READ))],
) -> list[IntegrationRead]:
    configs = ingestion_service.list_integrations(db, organization_id=auth.organization.id)
    return [ingestion_service.to_integration_read(c) for c in configs]


@router.patch(
    "/integrations/{integration_id}", response_model=IntegrationRead, tags=["integrations"]
)
def update_integration(
    integration_id: int,
    payload: IntegrationUpdate,
    request: Request,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INTEGRATION_MANAGE))],
) -> IntegrationRead:
    config = ingestion_service.update_integration(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        integration_id=integration_id,
        data=payload,
        ip_address=get_client_ip(request),
    )
    return ingestion_service.to_integration_read(config)


@router.post(
    "/integrations/{integration_id}/rotate-secret",
    response_model=SecretRotatedRead,
    tags=["integrations"],
)
def rotate_integration_secret(
    integration_id: int,
    request: Request,
    db: DbSession,
    settings: AppSettings,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INTEGRATION_MANAGE))],
) -> SecretRotatedRead:
    """Rotate signing secret; previous secret remains valid during the grace window."""
    config, new_secret, grace_until = ingestion_service.rotate_integration_secret(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        integration_id=integration_id,
        settings=settings,
        ip_address=get_client_ip(request),
    )
    return SecretRotatedRead(
        integration_id=config.id,
        signing_secret=new_secret,
        rotation_grace_until=grace_until,
    )


@router.post(
    "/integrations/{integration_id}/simulate",
    response_model=WebhookReceiptResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["integrations"],
)
def simulate_webhook(
    integration_id: int,
    payload: SimulateWebhookRequest,
    request: Request,
    db: DbSession,
    settings: AppSettings,
    enqueue_fn: Annotated[EnqueueFn, Depends(get_enqueue_fn)],
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INTEGRATION_MANAGE))],
) -> WebhookReceiptResponse:
    """Emit a deterministic local sample Alertmanager event marked ``is_simulated=True``."""
    return ingestion_service.simulate_alertmanager_webhook(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        integration_id=integration_id,
        request_data=payload,
        settings=settings,
        enqueue_fn=enqueue_fn,
        ip_address=get_client_ip(request),
    )


@router.get("/events", response_model=list[InboundEventRead], tags=["events"])
def list_events(
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.EVENT_READ))],
    status_filter: Annotated[InboundEventStatus | None, Query(alias="status")] = None,
    provider: str | None = None,
    is_simulated: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[InboundEvent]:
    return ingestion_service.list_events(
        db,
        organization_id=auth.organization.id,
        status_filter=status_filter,
        provider=provider,
        is_simulated=is_simulated,
        limit=limit,
    )


@router.get("/events/{event_id}", response_model=InboundEventRead, tags=["events"])
def get_event(
    event_id: int,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.EVENT_READ))],
) -> InboundEvent:
    return ingestion_service.get_event(db, organization_id=auth.organization.id, event_id=event_id)


@router.post("/events/{event_id}/replay", response_model=InboundEventRead, tags=["events"])
def replay_event(
    event_id: int,
    request: Request,
    db: DbSession,
    enqueue_fn: Annotated[EnqueueFn, Depends(get_enqueue_fn)],
    auth: Annotated[AuthContext, Depends(require_permission(Permission.EVENT_REPLAY))],
) -> InboundEvent:
    """Re-enqueue a failed or dead-lettered inbound event (audited)."""
    return ingestion_service.replay_event(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        event_id=event_id,
        enqueue_fn=enqueue_fn,
        ip_address=get_client_ip(request),
    )
