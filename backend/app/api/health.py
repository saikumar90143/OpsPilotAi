"""Liveness and readiness probes (unversioned by convention)."""

import logging
from http import HTTPStatus

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import CheckStatus, LivenessResponse, ReadinessResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

LEGACY_SERVICE_NAME = "opspilot-api"
DATABASE_CHECK = "database"


@router.get("", deprecated=True, summary="Legacy health check (use /health/live)")
def legacy_health_check() -> dict[str, str]:
    """Kept for backward compatibility with the Phase 0 API."""
    return {"status": "ok", "service": LEGACY_SERVICE_NAME}


@router.get("/live", response_model=LivenessResponse, summary="Liveness probe")
def liveness() -> LivenessResponse:
    """The process is up and serving HTTP. Performs no I/O."""
    return LivenessResponse()


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe",
    responses={HTTPStatus.SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
def readiness(response: Response, db: Session = Depends(get_db)) -> ReadinessResponse:
    """Ready only when the database answers ``SELECT 1``. Never exposes connection details."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.warning(
            "Readiness check failed: database unavailable (%s: %s)",
            type(exc).__name__,
            getattr(exc, "orig", exc),
        )
        response.status_code = HTTPStatus.SERVICE_UNAVAILABLE
        return ReadinessResponse(
            status="not_ready", checks={DATABASE_CHECK: CheckStatus.UNAVAILABLE}
        )
    return ReadinessResponse(status="ready", checks={DATABASE_CHECK: CheckStatus.OK})
