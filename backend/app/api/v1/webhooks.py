"""Inbound provider webhook receiver (Alertmanager)."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.api.deps import AppSettings, DbSession, get_client_ip
from app.api.errors import ERROR_RESPONSES
from app.core.errors import PayloadTooLargeError
from app.core.rate_limit import RateLimiter
from app.core.secrets import GITHUB_SIGNATURE_HEADER, SIGNATURE_HEADER
from app.schemas.ingestion import WebhookReceiptResponse
from app.services import github_service, ingestion_service
from app.services.ingestion_service import EnqueueFn
from app.worker import enqueue_inbound_event

webhook_rate_limiter = RateLimiter()

router = APIRouter(prefix="/webhooks", tags=["webhooks"], responses=ERROR_RESPONSES)


def get_enqueue_fn() -> EnqueueFn:
    return enqueue_inbound_event


@router.post(
    "/alertmanager/{endpoint_token}",
    response_model=WebhookReceiptResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def receive_alertmanager_webhook(
    endpoint_token: str,
    request: Request,
    db: DbSession,
    settings: AppSettings,
    enqueue_fn: Annotated[EnqueueFn, Depends(get_enqueue_fn)],
    x_opspilot_signature: Annotated[str | None, Header(alias=SIGNATURE_HEADER)] = None,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> WebhookReceiptResponse:
    """Validate, persist, and enqueue an inbound Prometheus Alertmanager webhook."""
    webhook_rate_limiter.check(
        f"webhook:{endpoint_token}",
        max_requests=settings.webhook_rate_limit_requests,
        window_seconds=settings.webhook_rate_limit_window_seconds,
    )

    raw_body = await request.body()
    if len(raw_body) > settings.webhook_max_bytes:
        raise PayloadTooLargeError(
            f"Webhook payload exceeds maximum size of {settings.webhook_max_bytes} bytes"
        )

    try:
        raw_payload = json.loads(raw_body)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid JSON payload"
        ) from exc

    if not isinstance(raw_payload, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Webhook payload must be a JSON object",
        )

    return ingestion_service.receive_alertmanager_webhook(
        db,
        endpoint_token=endpoint_token,
        raw_body=raw_body,
        raw_payload=raw_payload,
        signature_header=x_opspilot_signature,
        authorization_header=authorization,
        settings=settings,
        enqueue_fn=enqueue_fn,
        ip_address=get_client_ip(request),
    )


@router.post(
    "/github/{endpoint_token}",
    response_model=WebhookReceiptResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def receive_github_webhook(
    endpoint_token: str,
    request: Request,
    db: DbSession,
    settings: AppSettings,
    x_hub_signature_256: Annotated[str | None, Header(alias=GITHUB_SIGNATURE_HEADER)] = None,
    x_github_delivery: Annotated[str | None, Header(alias="X-GitHub-Delivery")] = None,
    x_github_event: Annotated[str | None, Header(alias="X-GitHub-Event")] = None,
) -> WebhookReceiptResponse:
    """Verify X-Hub-Signature-256 and record a deduplicated read-only GitHub webhook."""
    webhook_rate_limiter.check(
        f"github-webhook:{endpoint_token}",
        max_requests=settings.webhook_rate_limit_requests,
        window_seconds=settings.webhook_rate_limit_window_seconds,
    )
    raw_body = await request.body()
    if len(raw_body) > settings.webhook_max_bytes:
        raise PayloadTooLargeError(
            f"Webhook payload exceeds maximum size of {settings.webhook_max_bytes} bytes"
        )
    try:
        raw_payload = json.loads(raw_body)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid JSON payload"
        ) from exc
    if not isinstance(raw_payload, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Webhook payload must be a JSON object",
        )

    duplicate, receipt_id = github_service.receive_github_webhook(
        db,
        endpoint_token=endpoint_token,
        delivery_id=x_github_delivery,
        event_name=x_github_event,
        raw_body=raw_body,
        raw_payload=raw_payload,
        signature_header=x_hub_signature_256,
        settings=settings,
        ip_address=get_client_ip(request),
    )
    return WebhookReceiptResponse(
        accepted=True,
        duplicate=duplicate,
        event_ids=[receipt_id],
        status="duplicate" if duplicate else "recorded",
    )
