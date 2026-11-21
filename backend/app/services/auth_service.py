"""Authentication, refresh-token rotation, invitation acceptance, and session resolution."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ConflictError, UnauthorizedError
from app.core.permissions import Role
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_opaque_token,
    hash_opaque_token,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories import audit_repo, auth_repo

INVALID_CREDENTIALS_MESSAGE = "Invalid email or password"
INVALID_REFRESH_MESSAGE = "Invalid or expired refresh token"
INVALID_INVITE_MESSAGE = "Invalid or expired invitation"


@dataclass(frozen=True)
class AuthContext:
    user: User
    organization: Organization
    role: Role


@dataclass(frozen=True)
class IssuedSession:
    access_token: str
    refresh_token: str
    csrf_token: str
    context: AuthContext


def _as_utc(dt: datetime) -> datetime:
    # SQLite drops timezone offsets on round-trip; normalize naive datetimes to UTC.
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _issue_session_tokens(
    db: Session,
    *,
    user: User,
    organization: Organization,
    role: Role,
    settings: Settings,
    family_id: str | None = None,
) -> tuple[IssuedSession, RefreshToken]:
    raw_refresh = generate_opaque_token()
    token_row = RefreshToken(
        token_hash=hash_opaque_token(raw_refresh),
        family_id=family_id or uuid.uuid4().hex,
        user_id=user.id,
        organization_id=organization.id,
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(token_row)
    db.flush()

    access_token = create_access_token(
        user_id=user.id,
        organization_id=organization.id,
        role=role.value,
        settings=settings,
    )
    csrf_token = generate_opaque_token()
    session = IssuedSession(
        access_token=access_token,
        refresh_token=raw_refresh,
        csrf_token=csrf_token,
        context=AuthContext(user=user, organization=organization, role=role),
    )
    return session, token_row


def _resolve_login_membership(
    db: Session, *, user: User, organization_slug: str | None
) -> tuple[Organization, Membership] | None:
    if organization_slug:
        org = auth_repo.get_organization_by_slug(db, organization_slug.strip().lower())
        if org is None:
            return None
        membership = auth_repo.get_membership(db, organization_id=org.id, user_id=user.id)
        if membership is None:
            return None
        return org, membership

    membership = auth_repo.get_primary_membership_for_user(db, user.id)
    if membership is None:
        return None
    org = auth_repo.get_organization_by_id(db, membership.organization_id)
    if org is None:
        return None
    return org, membership


def authenticate_user(
    db: Session,
    *,
    email: str,
    password: str,
    organization_slug: str | None,
    settings: Settings,
    ip_address: str | None = None,
) -> IssuedSession:
    user = auth_repo.get_user_by_email(db, email)
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        audit_repo.append_event(
            db,
            action="auth.login.failure",
            actor_user_id=user.id if user is not None else None,
            ip_address=ip_address,
            metadata={"reason": "invalid_credentials"},
        )
        db.commit()
        raise UnauthorizedError(INVALID_CREDENTIALS_MESSAGE)

    resolved = _resolve_login_membership(db, user=user, organization_slug=organization_slug)
    if resolved is None:
        audit_repo.append_event(
            db,
            action="auth.login.failure",
            actor_user_id=user.id,
            ip_address=ip_address,
            metadata={"reason": "no_membership"},
        )
        db.commit()
        raise UnauthorizedError(INVALID_CREDENTIALS_MESSAGE)

    organization, membership = resolved
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    role = Role(membership.role)
    issued, _ = _issue_session_tokens(
        db, user=user, organization=organization, role=role, settings=settings
    )
    audit_repo.append_event(
        db,
        action="auth.login.success",
        organization_id=organization.id,
        actor_user_id=user.id,
        target_type="user",
        target_id=user.id,
        ip_address=ip_address,
        metadata={"role": role.value},
    )
    db.commit()
    return issued


def refresh_session(
    db: Session,
    *,
    raw_refresh_token: str | None,
    settings: Settings,
    ip_address: str | None = None,
) -> IssuedSession:
    if not raw_refresh_token:
        raise UnauthorizedError(INVALID_REFRESH_MESSAGE)

    token_row = auth_repo.get_refresh_token_by_hash(db, hash_opaque_token(raw_refresh_token))
    if token_row is None:
        raise UnauthorizedError(INVALID_REFRESH_MESSAGE)

    if token_row.revoked_at is not None:
        # Reuse of a rotated/revoked token: revoke the entire family immediately.
        auth_repo.revoke_refresh_token_family(db, family_id=token_row.family_id)
        audit_repo.append_event(
            db,
            action="auth.refresh.reuse_detected",
            organization_id=token_row.organization_id,
            actor_user_id=token_row.user_id,
            target_type="refresh_token",
            target_id=token_row.id,
            ip_address=ip_address,
        )
        db.commit()
        raise UnauthorizedError(INVALID_REFRESH_MESSAGE)

    now = datetime.now(UTC)
    if _as_utc(token_row.expires_at) <= now:
        token_row.revoked_at = now
        db.commit()
        raise UnauthorizedError(INVALID_REFRESH_MESSAGE)

    user = auth_repo.get_user_by_id(db, token_row.user_id)
    organization = auth_repo.get_organization_by_id(db, token_row.organization_id)
    membership = auth_repo.get_membership(
        db, organization_id=token_row.organization_id, user_id=token_row.user_id
    )
    if user is None or not user.is_active or organization is None or membership is None:
        auth_repo.revoke_refresh_token_family(db, family_id=token_row.family_id)
        db.commit()
        raise UnauthorizedError(INVALID_REFRESH_MESSAGE)

    role = Role(membership.role)
    issued, new_row = _issue_session_tokens(
        db,
        user=user,
        organization=organization,
        role=role,
        settings=settings,
        family_id=token_row.family_id,
    )
    token_row.revoked_at = now
    token_row.replaced_by_id = new_row.id
    audit_repo.append_event(
        db,
        action="auth.refresh.success",
        organization_id=organization.id,
        actor_user_id=user.id,
        target_type="refresh_token",
        target_id=new_row.id,
        ip_address=ip_address,
    )
    db.commit()
    return issued


def logout_session(
    db: Session,
    *,
    raw_refresh_token: str | None,
    actor_user_id: int | None = None,
    organization_id: int | None = None,
    ip_address: str | None = None,
) -> None:
    if raw_refresh_token:
        token_row = auth_repo.get_refresh_token_by_hash(db, hash_opaque_token(raw_refresh_token))
        if token_row is not None:
            auth_repo.revoke_refresh_token_family(db, family_id=token_row.family_id)
            actor_user_id = actor_user_id or token_row.user_id
            organization_id = organization_id or token_row.organization_id

    if actor_user_id is not None:
        audit_repo.append_event(
            db,
            action="auth.logout",
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            ip_address=ip_address,
        )
    db.commit()


def resolve_auth_context(db: Session, *, access_token: str, settings: Settings) -> AuthContext:
    claims = decode_access_token(access_token, settings)
    user = auth_repo.get_user_by_id(db, claims.user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Authentication required")

    organization = auth_repo.get_organization_by_id(db, claims.organization_id)
    if organization is None:
        raise UnauthorizedError("Authentication required")

    # Always re-verify active membership & role in DB so demotions/removals take effect immediately.
    membership = auth_repo.get_membership(db, organization_id=organization.id, user_id=user.id)
    if membership is None:
        raise UnauthorizedError("Authentication required")

    return AuthContext(user=user, organization=organization, role=Role(membership.role))


def accept_invitation(
    db: Session,
    *,
    raw_token: str,
    full_name: str,
    password: str,
    settings: Settings,
    ip_address: str | None = None,
) -> IssuedSession:
    invite = auth_repo.get_invitation_by_token_hash(db, hash_opaque_token(raw_token))
    now = datetime.now(UTC)
    if (
        invite is None
        or invite.revoked_at is not None
        or invite.accepted_at is not None
        or _as_utc(invite.expires_at) <= now
    ):
        raise UnauthorizedError(INVALID_INVITE_MESSAGE)

    role = Role(invite.role)
    if role is Role.OWNER:
        raise UnauthorizedError(INVALID_INVITE_MESSAGE)

    organization = auth_repo.get_organization_by_id(db, invite.organization_id)
    if organization is None:
        raise UnauthorizedError(INVALID_INVITE_MESSAGE)

    user = auth_repo.get_user_by_email(db, invite.email)
    if user is None:
        user = User(
            email=invite.email.strip().lower(),
            full_name=full_name.strip(),
            password_hash=hash_password(password),
            is_active=True,
        )
        db.add(user)
        db.flush()
    else:
        existing_membership = auth_repo.get_membership(
            db, organization_id=organization.id, user_id=user.id
        )
        if existing_membership is not None:
            raise ConflictError("User is already a member of this organization")

    membership = Membership(
        organization_id=organization.id,
        user_id=user.id,
        role=role.value,
    )
    db.add(membership)
    invite.accepted_at = now
    db.flush()

    issued, _ = _issue_session_tokens(
        db, user=user, organization=organization, role=role, settings=settings
    )
    audit_repo.append_event(
        db,
        action="invitation.accepted",
        organization_id=organization.id,
        actor_user_id=user.id,
        target_type="invitation",
        target_id=invite.id,
        ip_address=ip_address,
        metadata={"role": role.value},
    )
    db.commit()
    return issued
