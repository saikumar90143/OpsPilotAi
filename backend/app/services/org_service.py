"""Organization, membership, invitation, and audit-log use cases."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.permissions import Role
from app.core.security import generate_opaque_token, hash_opaque_token
from app.models.audit_log import AuditLog
from app.models.invitation import Invitation
from app.models.organization import Organization
from app.repositories import audit_repo, auth_repo
from app.schemas.auth import MembershipRead
from app.services.auth_service import AuthContext

MEMBERSHIP_NOT_FOUND = "Membership not found"
INVITATION_NOT_FOUND = "Invitation not found"


def update_organization(
    db: Session,
    *,
    auth: AuthContext,
    name: str,
    ip_address: str | None = None,
) -> Organization:
    previous_name = auth.organization.name
    auth.organization.name = name.strip()
    audit_repo.append_event(
        db,
        action="org.updated",
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        target_type="organization",
        target_id=auth.organization.id,
        ip_address=ip_address,
        metadata={"from_name": previous_name, "to_name": auth.organization.name},
    )
    db.commit()
    db.refresh(auth.organization)
    return auth.organization


def list_memberships(db: Session, *, organization_id: int) -> list[MembershipRead]:
    rows = auth_repo.list_memberships_for_org(db, organization_id=organization_id)
    return [
        MembershipRead(
            id=membership.id,
            organization_id=membership.organization_id,
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=Role(membership.role),
            is_active=user.is_active,
            created_at=membership.created_at,
        )
        for membership, user in rows
    ]


def update_membership_role(
    db: Session,
    *,
    auth: AuthContext,
    membership_id: int,
    new_role: Role,
    ip_address: str | None = None,
) -> MembershipRead:
    target = auth_repo.get_membership_by_id_and_org(
        db, organization_id=auth.organization.id, membership_id=membership_id
    )
    if target is None:
        raise NotFoundError(MEMBERSHIP_NOT_FOUND)

    current_target_role = Role(target.role)
    if auth.role is not Role.OWNER:
        if current_target_role in (Role.OWNER, Role.ADMIN) or new_role in (Role.OWNER, Role.ADMIN):
            raise ForbiddenError("Only organization owners can manage admin or owner roles")

    if current_target_role is Role.OWNER and new_role is not Role.OWNER:
        owner_count = sum(
            1
            for m, _ in auth_repo.list_memberships_for_org(db, organization_id=auth.organization.id)
            if m.role == Role.OWNER.value
        )
        if owner_count <= 1:
            raise ConflictError("Organization must retain at least one owner")

    if new_role is Role.OWNER and target.user_id != auth.user.id:
        # Ownership transfer: demote the acting owner to ADMIN.
        acting_membership = auth_repo.get_membership(
            db, organization_id=auth.organization.id, user_id=auth.user.id
        )
        if acting_membership is not None:
            acting_membership.role = Role.ADMIN.value

    target.role = new_role.value
    target_user = auth_repo.get_user_by_id(db, target.user_id)
    assert target_user is not None

    audit_repo.append_event(
        db,
        action="membership.role_updated",
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        target_type="membership",
        target_id=target.id,
        ip_address=ip_address,
        metadata={"from_role": current_target_role.value, "to_role": new_role.value},
    )
    db.commit()
    db.refresh(target)
    return MembershipRead(
        id=target.id,
        organization_id=target.organization_id,
        user_id=target_user.id,
        email=target_user.email,
        full_name=target_user.full_name,
        role=Role(target.role),
        is_active=target_user.is_active,
        created_at=target.created_at,
    )


def remove_membership(
    db: Session,
    *,
    auth: AuthContext,
    membership_id: int,
    ip_address: str | None = None,
) -> None:
    target = auth_repo.get_membership_by_id_and_org(
        db, organization_id=auth.organization.id, membership_id=membership_id
    )
    if target is None:
        raise NotFoundError(MEMBERSHIP_NOT_FOUND)

    target_role = Role(target.role)
    if target_role is Role.OWNER:
        raise ForbiddenError("Cannot remove an organization owner; transfer ownership first")
    if auth.role is not Role.OWNER and target_role is Role.ADMIN:
        raise ForbiddenError("Only organization owners can remove admins")

    audit_repo.append_event(
        db,
        action="membership.removed",
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        target_type="membership",
        target_id=target.id,
        ip_address=ip_address,
        metadata={"removed_user_id": target.user_id, "removed_role": target.role},
    )
    db.delete(target)
    db.commit()


def create_invitation(
    db: Session,
    *,
    auth: AuthContext,
    email: str,
    role: Role,
    settings: Settings,
    ip_address: str | None = None,
) -> tuple[Invitation, str]:
    normalized_email = email.strip().lower()
    if role is Role.OWNER:
        raise ForbiddenError("Cannot invite directly as owner")

    existing_user = auth_repo.get_user_by_email(db, normalized_email)
    if existing_user is not None:
        existing_membership = auth_repo.get_membership(
            db, organization_id=auth.organization.id, user_id=existing_user.id
        )
        if existing_membership is not None:
            raise ConflictError("User is already a member of this organization")

    raw_token = generate_opaque_token()
    invitation = Invitation(
        organization_id=auth.organization.id,
        email=normalized_email,
        role=role.value,
        token_hash=hash_opaque_token(raw_token),
        invited_by_user_id=auth.user.id,
        expires_at=datetime.now(UTC) + timedelta(hours=settings.invitation_expire_hours),
    )
    db.add(invitation)
    db.flush()

    audit_repo.append_event(
        db,
        action="invitation.created",
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        target_type="invitation",
        target_id=invitation.id,
        ip_address=ip_address,
        metadata={"role": role.value},
    )
    db.commit()
    db.refresh(invitation)
    return invitation, raw_token


def list_invitations(db: Session, *, organization_id: int) -> list[Invitation]:
    return auth_repo.list_invitations_for_org(db, organization_id=organization_id)


def revoke_invitation(
    db: Session,
    *,
    auth: AuthContext,
    invitation_id: int,
    ip_address: str | None = None,
) -> None:
    invitation = auth_repo.get_invitation_by_id_and_org(
        db, organization_id=auth.organization.id, invitation_id=invitation_id
    )
    if invitation is None:
        raise NotFoundError(INVITATION_NOT_FOUND)
    if invitation.revoked_at is None and invitation.accepted_at is None:
        invitation.revoked_at = datetime.now(UTC)
        audit_repo.append_event(
            db,
            action="invitation.revoked",
            organization_id=auth.organization.id,
            actor_user_id=auth.user.id,
            target_type="invitation",
            target_id=invitation.id,
            ip_address=ip_address,
        )
        db.commit()


def list_audit_logs(db: Session, *, organization_id: int, limit: int) -> list[AuditLog]:
    return audit_repo.list_by_org(db, organization_id=organization_id, limit=limit)
