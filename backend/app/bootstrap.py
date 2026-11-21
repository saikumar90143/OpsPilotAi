"""CLI-only local development bootstrap for demo organizations and users.

Usage (from ``backend/`` after ``alembic upgrade head``):
    python -m app.bootstrap

Never exposed as an HTTP endpoint and refuses to run when ``APP_ENV=production``.
"""

import os
import secrets
import sys
from dataclasses import dataclass

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.core.config import AppEnv, get_settings
from app.core.database import SessionLocal, engine
from app.core.permissions import Role
from app.core.security import hash_password
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.user import User
from app.repositories import auth_repo

EXIT_OK = 0
EXIT_ERROR = 1
BOOTSTRAP_PASSWORD_ENV = "BOOTSTRAP_DEMO_PASSWORD"


@dataclass(frozen=True)
class SeedAccount:
    org_slug: str
    org_name: str
    email: str
    full_name: str
    role: Role


DEMO_ACCOUNTS = (
    SeedAccount("acme-ops", "Acme Ops", "owner@acme.local", "Acme Owner", Role.OWNER),
    SeedAccount("acme-ops", "Acme Ops", "admin@acme.local", "Acme Admin", Role.ADMIN),
    SeedAccount("acme-ops", "Acme Ops", "engineer@acme.local", "Acme Engineer", Role.ENGINEER),
    SeedAccount("acme-ops", "Acme Ops", "viewer@acme.local", "Acme Viewer", Role.VIEWER),
    SeedAccount("beta-ops", "Beta Ops", "owner@beta.local", "Beta Owner", Role.OWNER),
)


def bootstrap_demo_data(db: Session, *, demo_password: str) -> int:
    """Idempotently create demo organizations, users, and memberships. Returns created count."""
    created_memberships = 0
    orgs: dict[str, Organization] = {}

    for account in DEMO_ACCOUNTS:
        org = orgs.get(account.org_slug) or auth_repo.get_organization_by_slug(db, account.org_slug)
        if org is None:
            org = Organization(name=account.org_name, slug=account.org_slug)
            db.add(org)
            db.flush()
        orgs[account.org_slug] = org

        user = auth_repo.get_user_by_email(db, account.email)
        if user is None:
            user = User(
                email=account.email,
                full_name=account.full_name,
                password_hash=hash_password(demo_password),
                is_active=True,
            )
            db.add(user)
            db.flush()

        membership = auth_repo.get_membership(db, organization_id=org.id, user_id=user.id)
        if membership is None:
            db.add(Membership(organization_id=org.id, user_id=user.id, role=account.role.value))
            created_memberships += 1

    db.commit()
    return created_memberships


def main() -> int:
    settings = get_settings()
    if settings.app_env is AppEnv.PRODUCTION:
        print("Refusing to run local bootstrap in production.", file=sys.stderr)
        return EXIT_ERROR

    inspector = inspect(engine)
    if not inspector.has_table(Organization.__tablename__):
        print("Database not migrated. Run 'alembic upgrade head' first.", file=sys.stderr)
        return EXIT_ERROR

    password = os.environ.get(BOOTSTRAP_PASSWORD_ENV) or secrets.token_urlsafe(16)
    with SessionLocal() as db:
        created = bootstrap_demo_data(db, demo_password=password)

    print(f"Bootstrap complete: created {created} membership(s).")
    if created > 0 and BOOTSTRAP_PASSWORD_ENV not in os.environ:
        print(f"Generated local dev password (save for login): {password}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
