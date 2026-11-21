"""Validated API schemas for incidents, timeline events, comments, and evidence."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.incident import (
    DEFAULT_SOURCE,
    EXTERNAL_ID_MAX_LENGTH,
    FINGERPRINT_MAX_LENGTH,
    SERVICE_MAX_LENGTH,
    SOURCE_MAX_LENGTH,
    TITLE_MAX_LENGTH,
    Environment,
    IncidentStatus,
    Severity,
)
from app.models.incident_details import (
    EVIDENCE_TITLE_MAX_LENGTH,
    EVIDENCE_URI_MAX_LENGTH,
    TAG_MAX_LENGTH,
    EvidenceKind,
)

TITLE_MIN_LENGTH = 4
SERVICE_MIN_LENGTH = 2
SOURCE_MIN_LENGTH = 2
DESCRIPTION_MAX_LENGTH = 10_000
COMMENT_MAX_LENGTH = 5_000
MAX_LIST_ITEMS = 25


class IncidentSortField(StrEnum):
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    SEVERITY = "severity"
    STATUS = "status"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class IncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(
        min_length=TITLE_MIN_LENGTH,
        max_length=TITLE_MAX_LENGTH,
        description="Short summary of the incident.",
        examples=["Checkout API returns errors"],
    )
    description: str = Field(
        default="",
        max_length=DESCRIPTION_MAX_LENGTH,
        description="Free-text details, symptoms, or context.",
    )
    service: str = Field(
        min_length=SERVICE_MIN_LENGTH,
        max_length=SERVICE_MAX_LENGTH,
        description="Primary affected service.",
        examples=["checkout-api"],
    )
    environment: Environment = Field(
        default=Environment.UNKNOWN,
        description="Deployment environment (production, staging, development, unknown).",
    )
    severity: Severity = Field(
        default=Severity.MEDIUM,
        description="Technical/business impact (critical, high, medium, low).",
    )
    source: str = Field(
        default=DEFAULT_SOURCE,
        min_length=SOURCE_MIN_LENGTH,
        max_length=SOURCE_MAX_LENGTH,
        description="Origin of the incident (manual, alertmanager, github, ...).",
    )
    external_source_id: str | None = Field(
        default=None, max_length=EXTERNAL_ID_MAX_LENGTH, description="External alert/event ID."
    )
    fingerprint: str | None = Field(
        default=None,
        max_length=FINGERPRINT_MAX_LENGTH,
        description="Deduplication key supplied by an integration.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Sanitized key-value metadata."
    )
    affected_services: list[str] = Field(
        default_factory=list,
        max_length=MAX_LIST_ITEMS,
        description="Additional affected services (primary service is always included).",
    )
    tags: list[str] = Field(
        default_factory=list,
        max_length=MAX_LIST_ITEMS,
        description="Normalized lowercase tags.",
    )


class IncidentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(
        default=None, min_length=TITLE_MIN_LENGTH, max_length=TITLE_MAX_LENGTH
    )
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX_LENGTH)
    service: str | None = Field(
        default=None, min_length=SERVICE_MIN_LENGTH, max_length=SERVICE_MAX_LENGTH
    )
    environment: Environment | None = None
    severity: Severity | None = None
    metadata: dict[str, Any] | None = None
    affected_services: list[str] | None = Field(default=None, max_length=MAX_LIST_ITEMS)
    tags: list[str] | None = Field(default=None, max_length=MAX_LIST_ITEMS)
    version: int | None = Field(
        default=None, ge=1, description="Expected version for optimistic concurrency."
    )


class IncidentStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: IncidentStatus = Field(description="Target workflow status.")
    version: int | None = Field(
        default=None, ge=1, description="Expected version for optimistic concurrency."
    )


class IncidentTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=500)
    version: int | None = Field(
        default=None, ge=1, description="Expected version for optimistic concurrency."
    )


class IncidentAssignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignee_user_id: int | None = Field(
        description="User ID of an active member in the same organization, or null to unassign."
    )
    version: int | None = Field(
        default=None, ge=1, description="Expected version for optimistic concurrency."
    )


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    created_by_user_id: int | None
    assignee_user_id: int | None
    title: str
    description: str
    service: str
    environment: Environment
    severity: Severity
    status: IncidentStatus
    source: str
    external_source_id: str | None
    fingerprint: str | None
    metadata: dict[str, Any] = Field(validation_alias="metadata_json")
    version: int
    affected_services: list[str]
    tags: list[str]
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    closed_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TimelineEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    incident_id: int
    actor_user_id: int | None
    event_type: str
    message: str
    details_json: dict[str, Any]
    created_at: datetime


class CommentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=COMMENT_MAX_LENGTH)


class CommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    incident_id: int
    author_user_id: int
    body: str
    created_at: datetime
    updated_at: datetime


class EvidenceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: EvidenceKind
    title: str = Field(min_length=2, max_length=EVIDENCE_TITLE_MAX_LENGTH)
    uri: str | None = Field(default=None, max_length=EVIDENCE_URI_MAX_LENGTH)
    summary: str = Field(default="", max_length=DESCRIPTION_MAX_LENGTH)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    incident_id: int
    added_by_user_id: int | None
    kind: EvidenceKind
    title: str
    uri: str | None
    summary: str
    metadata_json: dict[str, Any]
    created_at: datetime


__all__ = [
    "TAG_MAX_LENGTH",
    "CommentCreate",
    "CommentRead",
    "EvidenceCreate",
    "EvidenceRead",
    "IncidentAssignRequest",
    "IncidentCreate",
    "IncidentRead",
    "IncidentSortField",
    "IncidentStatusUpdate",
    "IncidentTransitionRequest",
    "IncidentUpdate",
    "SortOrder",
    "TimelineEventRead",
]
