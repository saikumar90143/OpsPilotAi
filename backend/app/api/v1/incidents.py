"""Incident endpoints: CRUD, lifecycle transitions, timeline, comments, evidence, search.

Every endpoint requires authentication and RBAC authorization, and scopes
all queries strictly to the caller's verified ``organization_id``.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status

from app.api.deps import AppSettings, DbSession, get_client_ip, require_permission
from app.api.errors import ERROR_RESPONSES
from app.core.errors import ConflictError
from app.core.permissions import Permission
from app.models.incident import Environment, Incident, IncidentStatus, Severity
from app.models.incident_details import (
    IncidentComment,
    IncidentEvidenceRef,
    IncidentTimelineEvent,
)
from app.repositories.incident_repo import IncidentListQuery
from app.schemas.github import CorrelateGitHubRequest, CorrelateGitHubResponse
from app.schemas.incident import (
    CommentCreate,
    CommentRead,
    EvidenceCreate,
    EvidenceRead,
    IncidentAssignRequest,
    IncidentCreate,
    IncidentRead,
    IncidentSortField,
    IncidentStatusUpdate,
    IncidentTransitionRequest,
    IncidentUpdate,
    SortOrder,
    TimelineEventRead,
)
from app.services import github_service
from app.services import incidents as incident_service
from app.services.auth_service import AuthContext

DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 100
TOTAL_COUNT_HEADER = "X-Total-Count"

router = APIRouter(prefix="/incidents", tags=["incidents"], responses=ERROR_RESPONSES)


def _resolve_expected_version(payload_version: int | None, if_match: str | None) -> int | None:
    if payload_version is not None:
        return payload_version
    if if_match is None:
        return None
    cleaned = if_match.strip().strip('"').removeprefix("W/").strip('"')
    if not cleaned.isdigit() or int(cleaned) < 1:
        raise ConflictError("Invalid If-Match version header")
    return int(cleaned)


@router.get("", response_model=list[IncidentRead])
def list_incidents(
    response: Response,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_READ))],
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
    status_filter: Annotated[IncidentStatus | None, Query(alias="status")] = None,
    severity: Severity | None = None,
    service: str | None = None,
    environment: Environment | None = None,
    assignee_user_id: int | None = None,
    tag: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    q: str | None = None,
    sort_by: IncidentSortField = IncidentSortField.CREATED_AT,
    sort_order: SortOrder = SortOrder.DESC,
) -> list[Incident]:
    """Return filtered, sorted, paginated active incidents; sets ``X-Total-Count``."""
    query = IncidentListQuery(
        limit=limit,
        offset=offset,
        status=status_filter,
        severity=severity,
        service=service,
        environment=environment,
        assignee_user_id=assignee_user_id,
        tag=tag,
        created_after=created_after,
        created_before=created_before,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    items, total = incident_service.list_incidents(
        db, organization_id=auth.organization.id, query=query
    )
    response.headers[TOTAL_COUNT_HEADER] = str(total)
    return items


@router.post("", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
def create_incident(
    payload: IncidentCreate,
    request: Request,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_WRITE))],
) -> Incident:
    """Create an incident scoped to the caller's organization."""
    return incident_service.create_incident(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        data=payload,
        ip_address=get_client_ip(request),
    )


@router.get("/{incident_id}", response_model=IncidentRead)
def get_incident(
    incident_id: int,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_READ))],
) -> Incident:
    """Fetch one incident by its numeric ID within the caller's organization."""
    return incident_service.get_incident(
        db, organization_id=auth.organization.id, incident_id=incident_id
    )


@router.patch("/{incident_id}", response_model=IncidentRead)
def update_incident(
    incident_id: int,
    payload: IncidentUpdate,
    request: Request,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_WRITE))],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> Incident:
    """Update incident details with optional optimistic concurrency check."""
    expected = _resolve_expected_version(payload.version, if_match)
    if expected is not None and payload.version is None:
        payload = payload.model_copy(update={"version": expected})
    return incident_service.update_incident(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        incident_id=incident_id,
        data=payload,
        ip_address=get_client_ip(request),
    )


@router.patch("/{incident_id}/status", response_model=IncidentRead)
def update_incident_status(
    incident_id: int,
    payload: IncidentStatusUpdate,
    request: Request,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_WRITE))],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> Incident:
    """Transition an incident's workflow status (state-machine enforced)."""
    return incident_service.transition_incident_status(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        incident_id=incident_id,
        target_status=payload.status,
        expected_version=_resolve_expected_version(payload.version, if_match),
        ip_address=get_client_ip(request),
    )


@router.post("/{incident_id}/acknowledge", response_model=IncidentRead)
def acknowledge_incident(
    incident_id: int,
    request: Request,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_WRITE))],
    payload: IncidentTransitionRequest | None = None,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> Incident:
    """Acknowledge an open or investigating incident."""
    body = payload or IncidentTransitionRequest()
    return incident_service.transition_incident_status(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        incident_id=incident_id,
        target_status=IncidentStatus.ACKNOWLEDGED,
        expected_version=_resolve_expected_version(body.version, if_match),
        note=body.note,
        ip_address=get_client_ip(request),
    )


@router.post("/{incident_id}/resolve", response_model=IncidentRead)
def resolve_incident(
    incident_id: int,
    request: Request,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_WRITE))],
    payload: IncidentTransitionRequest | None = None,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> Incident:
    """Resolve an incident."""
    body = payload or IncidentTransitionRequest()
    return incident_service.transition_incident_status(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        incident_id=incident_id,
        target_status=IncidentStatus.RESOLVED,
        expected_version=_resolve_expected_version(body.version, if_match),
        note=body.note,
        ip_address=get_client_ip(request),
    )


@router.post("/{incident_id}/reopen", response_model=IncidentRead)
def reopen_incident(
    incident_id: int,
    request: Request,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_WRITE))],
    payload: IncidentTransitionRequest | None = None,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> Incident:
    """Reopen a resolved or closed incident."""
    body = payload or IncidentTransitionRequest()
    return incident_service.transition_incident_status(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        incident_id=incident_id,
        target_status=IncidentStatus.OPEN,
        expected_version=_resolve_expected_version(body.version, if_match),
        note=body.note,
        ip_address=get_client_ip(request),
    )


@router.post("/{incident_id}/assign", response_model=IncidentRead)
def assign_incident(
    incident_id: int,
    payload: IncidentAssignRequest,
    request: Request,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_WRITE))],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> Incident:
    """Assign or unassign an incident to an active member of the same organization."""
    return incident_service.assign_incident(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        incident_id=incident_id,
        assignee_user_id=payload.assignee_user_id,
        expected_version=_resolve_expected_version(payload.version, if_match),
        ip_address=get_client_ip(request),
    )


@router.get("/{incident_id}/timeline", response_model=list[TimelineEventRead])
def list_incident_timeline(
    incident_id: int,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_READ))],
) -> list[IncidentTimelineEvent]:
    """Return chronological timeline events for an incident."""
    return incident_service.list_timeline(
        db, organization_id=auth.organization.id, incident_id=incident_id
    )


@router.get("/{incident_id}/comments", response_model=list[CommentRead])
def list_incident_comments(
    incident_id: int,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_READ))],
) -> list[IncidentComment]:
    """List notes/comments on an incident."""
    return incident_service.list_comments(
        db, organization_id=auth.organization.id, incident_id=incident_id
    )


@router.post(
    "/{incident_id}/comments",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
)
def add_incident_comment(
    incident_id: int,
    payload: CommentCreate,
    request: Request,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_WRITE))],
) -> IncidentComment:
    """Add a note/comment to an incident."""
    return incident_service.add_comment(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        incident_id=incident_id,
        data=payload,
        ip_address=get_client_ip(request),
    )


@router.get("/{incident_id}/evidence", response_model=list[EvidenceRead])
def list_incident_evidence(
    incident_id: int,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_READ))],
) -> list[IncidentEvidenceRef]:
    """List evidence references attached to an incident."""
    return incident_service.list_evidence(
        db, organization_id=auth.organization.id, incident_id=incident_id
    )


@router.post(
    "/{incident_id}/evidence",
    response_model=EvidenceRead,
    status_code=status.HTTP_201_CREATED,
)
def add_incident_evidence(
    incident_id: int,
    payload: EvidenceCreate,
    request: Request,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_WRITE))],
) -> IncidentEvidenceRef:
    """Attach an evidence reference to an incident."""
    return incident_service.add_evidence(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        incident_id=incident_id,
        data=payload,
        ip_address=get_client_ip(request),
    )


@router.post(
    "/{incident_id}/correlate-github",
    response_model=CorrelateGitHubResponse,
)
def correlate_github_evidence(
    incident_id: int,
    request: Request,
    db: DbSession,
    settings: AppSettings,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_WRITE))],
    payload: CorrelateGitHubRequest | None = None,
) -> CorrelateGitHubResponse:
    """Correlate incident service/time window with read-only GitHub evidence (hypothesis only)."""
    body = payload or CorrelateGitHubRequest()
    mode, repo, window_start, window_end, refs = github_service.correlate_incident(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        incident_id=incident_id,
        repository_override=body.repository,
        lookback_hours=body.lookback_hours,
        settings=settings,
        ip_address=get_client_ip(request),
    )
    return CorrelateGitHubResponse(
        mode=mode,
        repository=repo,
        disclaimer=github_service.HYPOTHESIS_DISCLAIMER,
        window_start=window_start,
        window_end=window_end,
        evidence_items=[EvidenceRead.model_validate(r) for r in refs],
    )


@router.delete("/{incident_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_incident(
    incident_id: int,
    request: Request,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_ARCHIVE))],
) -> None:
    """Soft-delete (archive) an incident within the caller's organization."""
    incident_service.archive_incident(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        incident_id=incident_id,
        ip_address=get_client_ip(request),
    )
