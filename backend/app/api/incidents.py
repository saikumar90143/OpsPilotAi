"""Incident endpoints: list, create, retrieve and update status."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.incident import Incident
from app.schemas.incident import IncidentCreate, IncidentRead, IncidentStatusUpdate

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentRead])
def list_incidents(
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[Incident]:
    """Return the newest incidents first."""
    statement = select(Incident).order_by(Incident.created_at.desc()).limit(limit)
    return list(db.scalars(statement).all())


@router.post("", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
def create_incident(
    payload: IncidentCreate,
    db: Session = Depends(get_db),
) -> Incident:
    """Create an incident from an operator or an integration."""
    incident = Incident(**payload.model_dump())
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident


@router.get("/{incident_id}", response_model=IncidentRead)
def get_incident(incident_id: int, db: Session = Depends(get_db)) -> Incident:
    """Fetch one incident by its numeric ID."""
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.patch("/{incident_id}/status", response_model=IncidentRead)
def update_incident_status(
    incident_id: int,
    payload: IncidentStatusUpdate,
    db: Session = Depends(get_db),
) -> Incident:
    """Update an incident's workflow status."""
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident.status = payload.status
    db.commit()
    db.refresh(incident)
    return incident
