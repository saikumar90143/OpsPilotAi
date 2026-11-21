"""Celery application and background task for inbound event processing."""

import logging

from celery import Celery
from kombu.exceptions import KombuError
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.errors import ServiceUnavailableError
from app.core.logging import configure_logging, request_id_var
from app.core.telemetry import get_tracer

logger = logging.getLogger(__name__)

_settings = get_settings()
configure_logging(_settings)

celery_app = Celery(
    "opspilot",
    broker=_settings.redis_url,
    backend=_settings.redis_url,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_soft_time_limit=30,
    task_time_limit=60,
    broker_connection_retry_on_startup=False,
    broker_transport_options={"socket_timeout": 2, "socket_connect_timeout": 2},
)


def enqueue_inbound_event(event_id: int, correlation_id: str) -> None:
    """Enqueue an inbound event onto Redis/Celery. Raises ServiceUnavailableError if unreachable."""
    try:
        process_inbound_event_task.apply_async(args=[event_id, correlation_id], retry=False)
    except (KombuError, RedisError, OSError) as exc:
        logger.warning("Failed to enqueue event %s: %s", event_id, type(exc).__name__)
        raise ServiceUnavailableError("Event queue is temporarily unavailable") from exc


@celery_app.task(bind=True, name="app.worker.process_inbound_event_task")
def process_inbound_event_task(self, event_id: int, correlation_id: str) -> str:  # type: ignore[no-untyped-def]
    from app.services import ingestion_service

    token = request_id_var.set(correlation_id)
    tracer = get_tracer("opspilot.worker")
    try:
        with tracer.start_as_current_span("worker.process_inbound_event"):
            with SessionLocal() as db:
                outcome = ingestion_service.execute_event_processing(db, event_id=event_id)
                if outcome.retry_countdown_seconds is not None:
                    raise self.retry(
                        exc=RuntimeError(outcome.error_message or "Transient event error"),
                        countdown=outcome.retry_countdown_seconds,
                        max_retries=outcome.max_attempts,
                    )
                return outcome.status.value
    finally:
        request_id_var.reset(token)
