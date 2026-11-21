"""Pydantic v2 schemas for authentication, organizations, memberships, invitations, and audit."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.permissions import Role
from app.core.security import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH
from app.models.organization import ORG_NAME_MAX_LENGTH
from app.models.user import EMAIL_MAX_LENGTH, FULL_NAME_MAX_LENGTH

InvitableRole = Literal[Role.ADMIN, Role.ENGINEER, Role.VIEWER]


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=EMAIL_MAX_LENGTH)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)
    organization_slug: str | None = Field(
        default=None,
        description="Optional slug when a user belongs to multiple organizations.",
    )


class AcceptInviteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=16, max_length=256)
    full_name: str = Field(min_length=2, max_length=FULL_NAME_MAX_LENGTH)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    created_at: datetime
    updated_at: datetime


class OrganizationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=ORG_NAME_MAX_LENGTH)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    is_active: bool
    created_at: datetime


class AuthSessionRead(BaseModel):
    user: UserRead
    organization: OrganizationRead
    role: Role


class MembershipRead(BaseModel):
    id: int
    organization_id: int
    user_id: int
    email: str
    full_name: str
    role: Role
    is_active: bool
    created_at: datetime


class MembershipRoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Role


class InvitationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=EMAIL_MAX_LENGTH)
    role: InvitableRole = Role.VIEWER


class InvitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    email: str
    role: Role
    invited_by_user_id: int
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class InvitationCreatedRead(InvitationRead):
    """Returned once at creation time so the caller can deliver the invite token out-of-band."""

    invite_token: str


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int | None
    actor_user_id: int | None
    action: str
    target_type: str | None
    target_id: str | None
    request_id: str
    ip_address: str | None
    metadata_json: dict[str, Any]
    created_at: datetime
