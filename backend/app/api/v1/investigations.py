"""Read-only AI investigation copilot API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import AppSettings, DbSession, require_permission
from app.api.errors import ERROR_RESPONSES
from app.core.permissions import Permission
from app.core.rate_limit import RateLimiter
from app.schemas.investigation import (
    AIStatusResponse,
    InvestigationFeedbackRequest,
    InvestigationRunOut,
    InvestigationStartRequest,
)
from app.services import investigation_service
from app.services.auth_service import AuthContext

router = APIRouter(tags=["investigations"], responses=ERROR_RESPONSES)
ai_rate_limiter = RateLimiter()


@router.get("/ai/status", response_model=AIStatusResponse)
def get_ai_status(
    db: DbSession,
    settings: AppSettings,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_READ))],
) -> AIStatusResponse:
    return investigation_service.get_ai_status(
        db, organization_id=auth.organization.id, settings=settings
    )


@router.post(
    "/incidents/{incident_id}/investigations",
    response_model=InvestigationRunOut,
    status_code=status.HTTP_201_CREATED,
)
def start_investigation(
    incident_id: int,
    payload: InvestigationStartRequest,
    db: DbSession,
    settings: AppSettings,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_WRITE))],
) -> InvestigationRunOut:
    ai_rate_limiter.check(
        f"ai:{auth.organization.id}:{auth.user.id}",
        max_requests=settings.ai_rate_limit_requests,
        window_seconds=settings.ai_rate_limit_window_seconds,
    )
    run = investigation_service.start_investigation(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        incident_id=incident_id,
        data=payload,
        settings=settings,
    )
    return InvestigationRunOut.model_validate(run)


@router.get(
    "/incidents/{incident_id}/investigations",
    response_model=list[InvestigationRunOut],
)
def list_incident_investigations(
    incident_id: int,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_READ))],
) -> list[InvestigationRunOut]:
    runs = investigation_service.list_incident_investigations(
        db, organization_id=auth.organization.id, incident_id=incident_id
    )
    return [InvestigationRunOut.model_validate(r) for r in runs]


@router.get("/investigations/{investigation_id}", response_model=InvestigationRunOut)
def get_investigation(
    investigation_id: int,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_READ))],
) -> InvestigationRunOut:
    run = investigation_service.get_investigation(
        db, organization_id=auth.organization.id, investigation_id=investigation_id
    )
    return InvestigationRunOut.model_validate(run)


@router.post("/investigations/{investigation_id}/cancel", response_model=InvestigationRunOut)
def cancel_investigation(
    investigation_id: int,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_WRITE))],
) -> InvestigationRunOut:
    run = investigation_service.cancel_investigation(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        investigation_id=investigation_id,
    )
    return InvestigationRunOut.model_validate(run)


@router.post("/investigations/{investigation_id}/feedback", response_model=InvestigationRunOut)
def submit_feedback(
    investigation_id: int,
    payload: InvestigationFeedbackRequest,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_READ))],
) -> InvestigationRunOut:
    run = investigation_service.submit_feedback(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        investigation_id=investigation_id,
        rating=payload.rating,
        note=payload.note,
    )
    return InvestigationRunOut.model_validate(run)
