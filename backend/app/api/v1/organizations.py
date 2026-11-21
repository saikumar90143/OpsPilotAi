"""Organization, membership, invitation, and audit-log endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import AppSettings, DbSession, get_client_ip, require_permission
from app.api.errors import ERROR_RESPONSES
from app.core.permissions import Permission, Role
from app.models.audit_log import AuditLog
from app.models.invitation import Invitation
from app.models.organization import Organization
from app.schemas.auth import (
    AuditLogRead,
    InvitationCreate,
    InvitationCreatedRead,
    InvitationRead,
    MembershipRead,
    MembershipRoleUpdate,
    OrganizationRead,
    OrganizationUpdate,
)
from app.services import org_service
from app.services.auth_service import AuthContext

DEFAULT_AUDIT_LIMIT = 50
MAX_AUDIT_LIMIT = 100

router = APIRouter(responses=ERROR_RESPONSES)


@router.get("/organizations/current", response_model=OrganizationRead, tags=["organizations"])
def get_current_organization(
    auth: Annotated[AuthContext, Depends(require_permission(Permission.ORG_READ))],
) -> Organization:
    return auth.organization


@router.patch("/organizations/current", response_model=OrganizationRead, tags=["organizations"])
def update_current_organization(
    payload: OrganizationUpdate,
    request: Request,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.ORG_UPDATE))],
) -> Organization:
    return org_service.update_organization(
        db, auth=auth, name=payload.name, ip_address=get_client_ip(request)
    )


@router.get("/memberships", response_model=list[MembershipRead], tags=["organizations"])
def list_memberships(
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.MEMBER_READ))],
) -> list[MembershipRead]:
    return org_service.list_memberships(db, organization_id=auth.organization.id)


@router.patch(
    "/memberships/{membership_id}/role", response_model=MembershipRead, tags=["organizations"]
)
def update_membership_role(
    membership_id: int,
    payload: MembershipRoleUpdate,
    request: Request,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.MEMBER_MANAGE))],
) -> MembershipRead:
    return org_service.update_membership_role(
        db,
        auth=auth,
        membership_id=membership_id,
        new_role=payload.role,
        ip_address=get_client_ip(request),
    )


@router.delete(
    "/memberships/{membership_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["organizations"],
)
def remove_membership(
    membership_id: int,
    request: Request,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.MEMBER_MANAGE))],
) -> None:
    org_service.remove_membership(
        db, auth=auth, membership_id=membership_id, ip_address=get_client_ip(request)
    )


@router.post(
    "/invitations",
    response_model=InvitationCreatedRead,
    status_code=status.HTTP_201_CREATED,
    tags=["organizations"],
)
def create_invitation(
    payload: InvitationCreate,
    request: Request,
    db: DbSession,
    settings: AppSettings,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INVITATION_MANAGE))],
) -> InvitationCreatedRead:
    invitation, raw_token = org_service.create_invitation(
        db,
        auth=auth,
        email=payload.email,
        role=Role(payload.role),
        settings=settings,
        ip_address=get_client_ip(request),
    )
    base = InvitationRead.model_validate(invitation)
    return InvitationCreatedRead(**base.model_dump(), invite_token=raw_token)


@router.get("/invitations", response_model=list[InvitationRead], tags=["organizations"])
def list_invitations(
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INVITATION_READ))],
) -> list[Invitation]:
    return org_service.list_invitations(db, organization_id=auth.organization.id)


@router.delete(
    "/invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["organizations"],
)
def revoke_invitation(
    invitation_id: int,
    request: Request,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INVITATION_MANAGE))],
) -> None:
    org_service.revoke_invitation(
        db, auth=auth, invitation_id=invitation_id, ip_address=get_client_ip(request)
    )


@router.get("/audit-logs", response_model=list[AuditLogRead], tags=["audit"])
def list_audit_logs(
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.AUDIT_READ))],
    limit: Annotated[int, Query(ge=1, le=MAX_AUDIT_LIMIT)] = DEFAULT_AUDIT_LIMIT,
) -> list[AuditLog]:
    return org_service.list_audit_logs(db, organization_id=auth.organization.id, limit=limit)
