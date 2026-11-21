"""Tenant-scoped incident persistence queries (filtering, sorting, pagination, concurrency)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import CursorResult, Select, case, func, or_, select, update
from sqlalchemy.orm import Session

from app.models.incident import Environment, Incident, IncidentStatus, Severity
from app.models.incident_details import IncidentTag
from app.schemas.incident import IncidentSortField, SortOrder

SEVERITY_RANK = case(
    (Incident.severity == Severity.CRITICAL.value, 4),
    (Incident.severity == Severity.HIGH.value, 3),
    (Incident.severity == Severity.MEDIUM.value, 2),
    (Incident.severity == Severity.LOW.value, 1),
    else_=0,
)


@dataclass(frozen=True)
class IncidentListQuery:
    limit: int = 50
    offset: int = 0
    status: IncidentStatus | None = None
    severity: Severity | None = None
    service: str | None = None
    environment: Environment | None = None
    assignee_user_id: int | None = None
    tag: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    q: str | None = None
    sort_by: IncidentSortField = IncidentSortField.CREATED_AT
    sort_order: SortOrder = SortOrder.DESC


def _apply_filters(
    stmt: Select[tuple[Incident]], *, organization_id: int, query: IncidentListQuery
) -> Select[tuple[Incident]]:
    stmt = stmt.where(Incident.organization_id == organization_id, Incident.archived_at.is_(None))
    if query.status is not None:
        stmt = stmt.where(Incident.status == query.status.value)
    if query.severity is not None:
        stmt = stmt.where(Incident.severity == query.severity.value)
    if query.service is not None:
        stmt = stmt.where(Incident.service == query.service)
    if query.environment is not None:
        stmt = stmt.where(Incident.environment == query.environment.value)
    if query.assignee_user_id is not None:
        stmt = stmt.where(Incident.assignee_user_id == query.assignee_user_id)
    if query.tag is not None:
        normalized_tag = query.tag.strip().lower()
        tag_subquery = select(IncidentTag.incident_id).where(
            IncidentTag.organization_id == organization_id,
            IncidentTag.tag == normalized_tag,
        )
        stmt = stmt.where(Incident.id.in_(tag_subquery))
    if query.created_after is not None:
        stmt = stmt.where(Incident.created_at >= query.created_after)
    if query.created_before is not None:
        stmt = stmt.where(Incident.created_at <= query.created_before)
    if query.q:
        pattern = f"%{query.q.strip()}%"
        stmt = stmt.where(
            or_(
                Incident.title.ilike(pattern),
                Incident.description.ilike(pattern),
                Incident.service.ilike(pattern),
            )
        )
    return stmt


def _sort_expression(sort_by: IncidentSortField) -> Any:
    if sort_by is IncidentSortField.UPDATED_AT:
        return Incident.updated_at
    if sort_by is IncidentSortField.SEVERITY:
        return SEVERITY_RANK
    if sort_by is IncidentSortField.STATUS:
        return Incident.status
    return Incident.created_at


def list_by_org(
    db: Session, *, organization_id: int, query: IncidentListQuery
) -> tuple[list[Incident], int]:
    base = _apply_filters(select(Incident), organization_id=organization_id, query=query)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0

    col = _sort_expression(query.sort_by)
    order = col.asc() if query.sort_order is SortOrder.ASC else col.desc()
    tie_breaker = Incident.id.asc() if query.sort_order is SortOrder.ASC else Incident.id.desc()

    stmt = base.order_by(order, tie_breaker).offset(query.offset).limit(query.limit)
    items = cast(list[Incident], list(db.scalars(stmt).all()))
    return items, total


def get_by_id_and_org(db: Session, *, organization_id: int, incident_id: int) -> Incident | None:
    statement = select(Incident).where(
        Incident.id == incident_id,
        Incident.organization_id == organization_id,
        Incident.archived_at.is_(None),
    )
    return db.scalar(statement)


def atomic_bump_version(
    db: Session, *, organization_id: int, incident_id: int, expected_version: int
) -> bool:
    """Atomically increment version only if expected_version still matches in the DB."""
    result = cast(
        CursorResult[Any],
        db.execute(
            update(Incident)
            .where(
                Incident.id == incident_id,
                Incident.organization_id == organization_id,
                Incident.version == expected_version,
                Incident.archived_at.is_(None),
            )
            .values(version=Incident.version + 1)
        ),
    )
    return (result.rowcount or 0) == 1


def mark_archived(incident: Incident) -> Incident:
    incident.archived_at = datetime.now(UTC)
    return incident
