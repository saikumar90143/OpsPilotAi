"""Persistence queries for users, organizations, memberships, tokens, and invitations."""

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.invitation import Invitation
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.refresh_token import RefreshToken
from app.models.user import User


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_user_by_email(db: Session, email: str) -> User | None:
    normalized = email.strip().lower()
    return db.scalar(select(User).where(User.email == normalized))


def get_organization_by_id(db: Session, organization_id: int) -> Organization | None:
    return db.get(Organization, organization_id)


def get_organization_by_slug(db: Session, slug: str) -> Organization | None:
    return db.scalar(select(Organization).where(Organization.slug == slug))


def get_membership(db: Session, *, organization_id: int, user_id: int) -> Membership | None:
    return db.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == user_id,
        )
    )


def get_primary_membership_for_user(db: Session, user_id: int) -> Membership | None:
    return db.scalar(
        select(Membership).where(Membership.user_id == user_id).order_by(Membership.id.asc())
    )


def list_memberships_for_org(db: Session, *, organization_id: int) -> list[tuple[Membership, User]]:
    statement = (
        select(Membership, User)
        .join(User, Membership.user_id == User.id)
        .where(Membership.organization_id == organization_id)
        .order_by(Membership.id.asc())
    )
    return [(m, u) for m, u in db.execute(statement).all()]


def get_membership_by_id_and_org(
    db: Session, *, organization_id: int, membership_id: int
) -> Membership | None:
    return db.scalar(
        select(Membership).where(
            Membership.id == membership_id,
            Membership.organization_id == organization_id,
        )
    )


def get_refresh_token_by_hash(db: Session, token_hash: str) -> RefreshToken | None:
    return db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))


def revoke_refresh_token_family(db: Session, *, family_id: str) -> None:
    now = datetime.now(UTC)
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )


def get_invitation_by_token_hash(db: Session, token_hash: str) -> Invitation | None:
    return db.scalar(select(Invitation).where(Invitation.token_hash == token_hash))


def get_invitation_by_id_and_org(
    db: Session, *, organization_id: int, invitation_id: int
) -> Invitation | None:
    return db.scalar(
        select(Invitation).where(
            Invitation.id == invitation_id,
            Invitation.organization_id == organization_id,
        )
    )


def list_invitations_for_org(db: Session, *, organization_id: int) -> list[Invitation]:
    statement = (
        select(Invitation)
        .where(Invitation.organization_id == organization_id)
        .order_by(Invitation.created_at.desc(), Invitation.id.desc())
    )
    return list(db.scalars(statement).all())
