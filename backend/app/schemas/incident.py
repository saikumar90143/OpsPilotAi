"""Validated API schemas for incidents."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["low", "medium", "high", "critical"]
IncidentStatus = Literal["open", "investigating", "resolved", "closed"]


class IncidentCreate(BaseModel):
    title: str = Field(min_length=4, max_length=180)
    description: str = Field(default="", max_length=10_000)
    service: str = Field(min_length=2, max_length=100)
    severity: Severity = "medium"
    source: str = Field(default="manual", min_length=2, max_length=50)


class IncidentStatusUpdate(BaseModel):
    status: IncidentStatus


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    service: str
    severity: Severity
    status: IncidentStatus
    source: str
    created_at: datetime
    updated_at: datetime
