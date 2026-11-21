"""Tenant-scoped incident domain service: lifecycle state machine, concurrency, timeline."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.core.telemetry import INCIDENT_TTA_SECONDS, INCIDENT_TTR_SECONDS
from app.models.incident import Incident, IncidentStatus
from app.models.incident_details import (
    IncidentAffectedService,
    IncidentComment,
    IncidentEvidenceRef,
    IncidentTag,
    IncidentTimelineEvent,
)
from app.repositories import audit_repo, auth_repo, incident_repo
from app.repositories.incident_repo import IncidentListQuery
from app.schemas.incident import (
    CommentCreate,
    EvidenceCreate,
    IncidentCreate,
    IncidentUpdate,
)

INCIDENT_NOT_FOUND_MESSAGE = "Incident not found"
CONCURRENT_MODIFICATION_MESSAGE = "Incident was modified concurrently; refresh and retry"
ASSIGNEE_NOT_FOUND_MESSAGE = "Assignee is not a member of this organization"

ALLOWED_TRANSITIONS: dict[IncidentStatus, frozenset[IncidentStatus]] = {
    IncidentStatus.OPEN: frozenset(
        {
            IncidentStatus.ACKNOWLEDGED,
            IncidentStatus.INVESTIGATING,
            IncidentStatus.RESOLVED,
            IncidentStatus.CLOSED,
        }
    ),
    IncidentStatus.ACKNOWLEDGED: frozenset(
        {
            IncidentStatus.INVESTIGATING,
            IncidentStatus.RESOLVED,
            IncidentStatus.CLOSED,
        }
    ),
    IncidentStatus.INVESTIGATING: frozenset(
        {
            IncidentStatus.ACKNOWLEDGED,
            IncidentStatus.RESOLVED,
            IncidentStatus.CLOSED,
        }
    ),
    IncidentStatus.RESOLVED: frozenset(
        {
            IncidentStatus.OPEN,
            IncidentStatus.INVESTIGATING,
            IncidentStatus.CLOSED,
        }
    ),
    IncidentStatus.CLOSED: frozenset(
        {
            IncidentStatus.OPEN,
        }
    ),
}


def _normalize_services(primary_service: str, extra: list[str]) -> list[str]:
    seen: list[str] = []
    for item in [primary_service, *extra]:
        cleaned = item.strip()
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen


def _normalize_tags(tags: list[str]) -> list[str]:
    seen: list[str] = []
    for item in tags:
        cleaned = item.strip().lower()
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen


def _record_timeline_and_audit(
    db: Session,
    *,
    organization_id: int,
    incident_id: int,
    actor_user_id: int,
    event_type: str,
    message: str,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    sanitized = audit_repo.sanitize_metadata(details)
    db.add(
        IncidentTimelineEvent(
            organization_id=organization_id,
            incident_id=incident_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            message=message,
            details_json=sanitized,
        )
    )
    audit_repo.append_event(
        db,
        action=event_type,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        target_type="incident",
        target_id=incident_id,
        ip_address=ip_address,
        metadata=sanitized,
    )


def _enforce_version(db: Session, *, incident: Incident, expected_version: int | None) -> None:
    target_version = expected_version if expected_version is not None else incident.version
    if expected_version is not None and expected_version != incident.version:
        raise ConflictError(CONCURRENT_MODIFICATION_MESSAGE)
    updated = incident_repo.atomic_bump_version(
        db,
        organization_id=incident.organization_id,
        incident_id=incident.id,
        expected_version=target_version,
    )
    if not updated:
        db.rollback()
        raise ConflictError(CONCURRENT_MODIFICATION_MESSAGE)
    db.refresh(incident, attribute_names=["version"])


def list_incidents(
    db: Session, *, organization_id: int, query: IncidentListQuery
) -> tuple[list[Incident], int]:
    """Return filtered/sorted non-archived incidents for the organization and total count."""
    return incident_repo.list_by_org(db, organization_id=organization_id, query=query)


def get_incident(db: Session, *, organization_id: int, incident_id: int) -> Incident:
    incident = incident_repo.get_by_id_and_org(
        db, organization_id=organization_id, incident_id=incident_id
    )
    if incident is None:
        raise NotFoundError(INCIDENT_NOT_FOUND_MESSAGE)
    return incident


def create_incident(
    db: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    data: IncidentCreate,
    ip_address: str | None = None,
) -> Incident:
    incident = Incident(
        organization_id=organization_id,
        created_by_user_id=actor_user_id,
        title=data.title,
        description=data.description,
        service=data.service,
        environment=data.environment.value,
        severity=data.severity.value,
        source=data.source,
        external_source_id=data.external_source_id,
        fingerprint=data.fingerprint,
        metadata_json=audit_repo.sanitize_metadata(data.metadata),
    )
    db.add(incident)
    db.flush()

    for svc in _normalize_services(data.service, data.affected_services):
        db.add(
            IncidentAffectedService(
                organization_id=organization_id, incident_id=incident.id, service_name=svc
            )
        )
    for tag in _normalize_tags(data.tags):
        db.add(IncidentTag(organization_id=organization_id, incident_id=incident.id, tag=tag))

    _record_timeline_and_audit(
        db,
        organization_id=organization_id,
        incident_id=incident.id,
        actor_user_id=actor_user_id,
        event_type="incident.created",
        message=f"Incident created with severity '{incident.severity}'",
        details={"service": incident.service, "severity": incident.severity},
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(incident)
    return incident


def update_incident(
    db: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    incident_id: int,
    data: IncidentUpdate,
    ip_address: str | None = None,
) -> Incident:
    incident = get_incident(db, organization_id=organization_id, incident_id=incident_id)
    _enforce_version(db, incident=incident, expected_version=data.version)

    changed: list[str] = []
    if data.title is not None:
        incident.title = data.title
        changed.append("title")
    if data.description is not None:
        incident.description = data.description
        changed.append("description")
    if data.service is not None:
        incident.service = data.service
        changed.append("service")
    if data.environment is not None:
        incident.environment = data.environment.value
        changed.append("environment")
    if data.severity is not None:
        incident.severity = data.severity.value
        changed.append("severity")
    if data.metadata is not None:
        incident.metadata_json = audit_repo.sanitize_metadata(data.metadata)
        changed.append("metadata")

    if data.affected_services is not None or data.service is not None:
        extra = (
            data.affected_services
            if data.affected_services is not None
            else incident.affected_services
        )
        incident.affected_service_rows.clear()
        db.flush()
        for svc in _normalize_services(incident.service, extra):
            incident.affected_service_rows.append(
                IncidentAffectedService(
                    organization_id=organization_id, incident_id=incident.id, service_name=svc
                )
            )
        if data.affected_services is not None:
            changed.append("affected_services")

    if data.tags is not None:
        incident.tag_rows.clear()
        db.flush()
        for tag in _normalize_tags(data.tags):
            incident.tag_rows.append(
                IncidentTag(organization_id=organization_id, incident_id=incident.id, tag=tag)
            )
        changed.append("tags")

    _record_timeline_and_audit(
        db,
        organization_id=organization_id,
        incident_id=incident.id,
        actor_user_id=actor_user_id,
        event_type="incident.updated",
        message=f"Updated fields: {', '.join(changed) if changed else 'none'}",
        details={"changed_fields": changed},
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(incident)
    return incident


def transition_incident_status(
    db: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    incident_id: int,
    target_status: IncidentStatus,
    expected_version: int | None = None,
    note: str | None = None,
    ip_address: str | None = None,
) -> Incident:
    incident = get_incident(db, organization_id=organization_id, incident_id=incident_id)
    current = IncidentStatus(incident.status)
    allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
    if target_status not in allowed:
        raise ConflictError(
            f"Invalid status transition from '{current.value}' to '{target_status.value}'"
        )

    _enforce_version(db, incident=incident, expected_version=expected_version)

    now = datetime.now(UTC)
    incident.status = target_status.value
    if target_status is IncidentStatus.ACKNOWLEDGED and incident.acknowledged_at is None:
        incident.acknowledged_at = now
        created_utc = (
            incident.created_at.replace(tzinfo=UTC)
            if incident.created_at.tzinfo is None
            else incident.created_at.astimezone(UTC)
        )
        INCIDENT_TTA_SECONDS.labels(severity=incident.severity).observe(
            max(0.0, (now - created_utc).total_seconds())
        )
    elif target_status is IncidentStatus.RESOLVED:
        incident.resolved_at = now
        created_utc = (
            incident.created_at.replace(tzinfo=UTC)
            if incident.created_at.tzinfo is None
            else incident.created_at.astimezone(UTC)
        )
        INCIDENT_TTR_SECONDS.labels(severity=incident.severity).observe(
            max(0.0, (now - created_utc).total_seconds())
        )
    elif target_status is IncidentStatus.CLOSED:
        incident.closed_at = now
    elif target_status is IncidentStatus.OPEN:
        incident.resolved_at = None
        incident.closed_at = None

    event_type = (
        "incident.reopened"
        if target_status is IncidentStatus.OPEN
        and current in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED)
        else "incident.status_updated"
    )
    details: dict[str, Any] = {"from": current.value, "to": target_status.value}
    if note:
        details["note"] = note
    _record_timeline_and_audit(
        db,
        organization_id=organization_id,
        incident_id=incident.id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        message=f"Status changed from '{current.value}' to '{target_status.value}'",
        details=details,
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(incident)
    return incident


def assign_incident(
    db: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    incident_id: int,
    assignee_user_id: int | None,
    expected_version: int | None = None,
    ip_address: str | None = None,
) -> Incident:
    incident = get_incident(db, organization_id=organization_id, incident_id=incident_id)

    if assignee_user_id is not None:
        membership = auth_repo.get_membership(
            db, organization_id=organization_id, user_id=assignee_user_id
        )
        if membership is None:
            raise NotFoundError(ASSIGNEE_NOT_FOUND_MESSAGE)

    _enforce_version(db, incident=incident, expected_version=expected_version)
    previous_assignee = incident.assignee_user_id
    incident.assignee_user_id = assignee_user_id

    _record_timeline_and_audit(
        db,
        organization_id=organization_id,
        incident_id=incident.id,
        actor_user_id=actor_user_id,
        event_type="incident.assigned",
        message=(
            f"Assigned to user {assignee_user_id}"
            if assignee_user_id is not None
            else "Incident unassigned"
        ),
        details={"from_user_id": previous_assignee, "to_user_id": assignee_user_id},
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(incident)
    return incident


def archive_incident(
    db: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    incident_id: int,
    ip_address: str | None = None,
) -> Incident:
    incident = get_incident(db, organization_id=organization_id, incident_id=incident_id)
    incident_repo.mark_archived(incident)
    _record_timeline_and_audit(
        db,
        organization_id=organization_id,
        incident_id=incident.id,
        actor_user_id=actor_user_id,
        event_type="incident.archived",
        message="Incident archived",
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(incident)
    return incident


def list_timeline(
    db: Session, *, organization_id: int, incident_id: int
) -> list[IncidentTimelineEvent]:
    get_incident(db, organization_id=organization_id, incident_id=incident_id)
    stmt = (
        select(IncidentTimelineEvent)
        .where(
            IncidentTimelineEvent.organization_id == organization_id,
            IncidentTimelineEvent.incident_id == incident_id,
        )
        .order_by(IncidentTimelineEvent.created_at.asc(), IncidentTimelineEvent.id.asc())
    )
    return list(db.scalars(stmt).all())


def list_comments(db: Session, *, organization_id: int, incident_id: int) -> list[IncidentComment]:
    get_incident(db, organization_id=organization_id, incident_id=incident_id)
    stmt = (
        select(IncidentComment)
        .where(
            IncidentComment.organization_id == organization_id,
            IncidentComment.incident_id == incident_id,
        )
        .order_by(IncidentComment.created_at.asc(), IncidentComment.id.asc())
    )
    return list(db.scalars(stmt).all())


def add_comment(
    db: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    incident_id: int,
    data: CommentCreate,
    ip_address: str | None = None,
) -> IncidentComment:
    get_incident(db, organization_id=organization_id, incident_id=incident_id)
    comment = IncidentComment(
        organization_id=organization_id,
        incident_id=incident_id,
        author_user_id=actor_user_id,
        body=data.body,
    )
    db.add(comment)
    db.flush()
    _record_timeline_and_audit(
        db,
        organization_id=organization_id,
        incident_id=incident_id,
        actor_user_id=actor_user_id,
        event_type="incident.comment_added",
        message="Comment added",
        details={"comment_id": comment.id},
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(comment)
    return comment


def list_evidence(
    db: Session, *, organization_id: int, incident_id: int
) -> list[IncidentEvidenceRef]:
    get_incident(db, organization_id=organization_id, incident_id=incident_id)
    stmt = (
        select(IncidentEvidenceRef)
        .where(
            IncidentEvidenceRef.organization_id == organization_id,
            IncidentEvidenceRef.incident_id == incident_id,
        )
        .order_by(IncidentEvidenceRef.created_at.asc(), IncidentEvidenceRef.id.asc())
    )
    return list(db.scalars(stmt).all())


def add_evidence(
    db: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    incident_id: int,
    data: EvidenceCreate,
    ip_address: str | None = None,
) -> IncidentEvidenceRef:
    get_incident(db, organization_id=organization_id, incident_id=incident_id)
    evidence = IncidentEvidenceRef(
        organization_id=organization_id,
        incident_id=incident_id,
        added_by_user_id=actor_user_id,
        kind=data.kind.value,
        title=data.title,
        uri=data.uri,
        summary=data.summary,
        metadata_json=audit_repo.sanitize_metadata(data.metadata),
    )
    db.add(evidence)
    db.flush()
    _record_timeline_and_audit(
        db,
        organization_id=organization_id,
        incident_id=incident_id,
        actor_user_id=actor_user_id,
        event_type="incident.evidence_added",
        message=f"Attached {data.kind.value} evidence: {data.title}",
        details={"evidence_id": evidence.id, "kind": data.kind.value},
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(evidence)
    return evidence
