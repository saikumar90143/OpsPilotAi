"""FastAPI application factory and ASGI entry point (``app.main:app``)."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.deps import CSRF_HEADER_NAME
from app.api.errors import register_exception_handlers
from app.api.health import router as health_router
from app.api.middleware import RequestContextMiddleware
from app.api.v1 import api_v1_router
from app.api.v1.incidents import TOTAL_COUNT_HEADER
from app.core.config import Settings, get_settings
from app.core.database import engine
from app.core.logging import REQUEST_ID_HEADER, configure_logging
from app.core.telemetry import instrument_app, render_prometheus_metrics

logger = logging.getLogger(__name__)

API_DESCRIPTION = (
    "Evidence-backed incident investigation and workflow automation platform.\n\n"
    "Schema is managed by Alembic (`alembic upgrade head`); the app never creates tables. "
    "All error responses use `{error, message, request_id}`."
)
OPENAPI_TAGS = [
    {"name": "health", "description": "Liveness and readiness probes."},
    {"name": "auth", "description": "Cookie-based authentication, refresh, and invitations."},
    {"name": "organizations", "description": "Tenant organization and membership management."},
    {"name": "incidents", "description": "Tenant-scoped incident lifecycle management."},
    {"name": "integrations", "description": "Tenant integration configs and webhook simulator."},
    {"name": "github", "description": "Read-only GitHub evidence connector."},
    {
        "name": "evidence",
        "description": "Structured application logs and engineering knowledge base.",
    },
    {"name": "investigations", "description": "Read-only AI investigation copilot."},
    {"name": "actions", "description": "Human-gated external write actions (Jira & Slack)."},
    {"name": "webhooks", "description": "Inbound provider webhook endpoints."},
    {"name": "events", "description": "Inbound event receipts, dead-letter review, and replay."},
    {"name": "audit", "description": "Append-only security and domain audit log."},
]
CORS_METHODS = ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOW_HEADERS = ["Content-Type", CSRF_HEADER_NAME, REQUEST_ID_HEADER, "Authorization"]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "Starting %s v%s (env=%s, database=%s)",
            settings.app_name,
            __version__,
            settings.app_env,
            settings.database_url_redacted,
        )
        yield
        logger.info("Shutting down %s", settings.app_name)

    app = FastAPI(
        title=settings.app_name,
        description=API_DESCRIPTION,
        version=__version__,
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
    )

    # Middleware added last runs first: request context wraps CORS so every
    # response (including preflight) carries X-Request-ID.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=CORS_METHODS,
        allow_headers=CORS_ALLOW_HEADERS,
        expose_headers=[REQUEST_ID_HEADER, TOTAL_COUNT_HEADER],
    )
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(api_v1_router)

    @app.get("/metrics", include_in_schema=False)
    def prometheus_metrics() -> Response:
        body, content_type = render_prometheus_metrics()
        return Response(content=body, media_type=content_type)

    instrument_app(app, engine, settings)
    return app


app = create_app()
