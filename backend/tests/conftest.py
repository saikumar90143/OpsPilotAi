"""Shared fixtures.

Test isolation: APP_ENV/DATABASE_URL/JWT_SECRET_KEY are forced *before* the app
is imported, so tests never read a developer's DATABASE_URL and never touch
``opspilot.db``.
PostgreSQL tests (``@pytest.mark.postgres``) run only when TEST_POSTGRES_URL is set
(environment variable or root ``.env``); otherwise they are reported as SKIPPED.
"""

import os

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET_KEY"] = "test-only-jwt-secret-key-at-least-32-chars"

from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.api.v1.investigations import ai_rate_limiter
from app.api.v1.webhooks import webhook_rate_limiter
from app.core.config import REPO_ROOT_ENV_FILE
from app.core.database import Base, get_db
from app.core.permissions import Role
from app.core.rate_limit import auth_rate_limiter
from app.core.security import hash_password
from app.main import app
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.user import User

TEST_POSTGRES_URL_VAR = "TEST_POSTGRES_URL"
TEST_PASSWORD = "TestPassword123!"


def get_test_postgres_url() -> str | None:
    url = os.environ.get(TEST_POSTGRES_URL_VAR)
    if url:
        return url
    return dotenv_values(REPO_ROOT_ENV_FILE).get(TEST_POSTGRES_URL_VAR) or None


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if get_test_postgres_url():
        return
    skip = pytest.mark.skip(reason=f"{TEST_POSTGRES_URL_VAR} not set; PostgreSQL tests not run")
    for item in items:
        if "postgres" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> Iterator[None]:
    auth_rate_limiter.reset()
    webhook_rate_limiter.reset()
    ai_rate_limiter.reset()
    yield
    auth_rate_limiter.reset()
    webhook_rate_limiter.reset()
    ai_rate_limiter.reset()


@pytest.fixture(scope="session")
def test_postgres_url() -> str:
    url = get_test_postgres_url()
    if not url:  # pragma: no cover - collection hook already skips these tests
        pytest.skip(f"{TEST_POSTGRES_URL_VAR} not set")
    return url


@pytest.fixture()
def sqlite_engine() -> Iterator[Engine]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def session_factory(sqlite_engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=sqlite_engine, autoflush=False)


@pytest.fixture()
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        db = session_factory()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@dataclass(frozen=True)
class SeededTenants:
    org_a: Organization
    org_b: Organization
    a_owner: User
    a_admin: User
    a_engineer: User
    a_viewer: User
    b_owner: User


def seed_tenants(db: Session) -> SeededTenants:
    org_a = Organization(name="Acme Ops", slug="acme-ops")
    org_b = Organization(name="Beta Ops", slug="beta-ops")
    db.add_all([org_a, org_b])
    db.flush()

    pw_hash = hash_password(TEST_PASSWORD)
    a_owner = User(email="owner@acme.local", full_name="Acme Owner", password_hash=pw_hash)
    a_admin = User(email="admin@acme.local", full_name="Acme Admin", password_hash=pw_hash)
    a_engineer = User(email="eng@acme.local", full_name="Acme Engineer", password_hash=pw_hash)
    a_viewer = User(email="viewer@acme.local", full_name="Acme Viewer", password_hash=pw_hash)
    b_owner = User(email="owner@beta.local", full_name="Beta Owner", password_hash=pw_hash)
    db.add_all([a_owner, a_admin, a_engineer, a_viewer, b_owner])
    db.flush()

    db.add_all(
        [
            Membership(organization_id=org_a.id, user_id=a_owner.id, role=Role.OWNER.value),
            Membership(organization_id=org_a.id, user_id=a_admin.id, role=Role.ADMIN.value),
            Membership(organization_id=org_a.id, user_id=a_engineer.id, role=Role.ENGINEER.value),
            Membership(organization_id=org_a.id, user_id=a_viewer.id, role=Role.VIEWER.value),
            Membership(organization_id=org_b.id, user_id=b_owner.id, role=Role.OWNER.value),
        ]
    )
    db.commit()
    for obj in (org_a, org_b, a_owner, a_admin, a_engineer, a_viewer, b_owner):
        db.refresh(obj)
    return SeededTenants(
        org_a=org_a,
        org_b=org_b,
        a_owner=a_owner,
        a_admin=a_admin,
        a_engineer=a_engineer,
        a_viewer=a_viewer,
        b_owner=b_owner,
    )


@pytest.fixture()
def tenants(session_factory: sessionmaker[Session]) -> SeededTenants:
    with session_factory() as db:
        return seed_tenants(db)


def login_client(
    test_client: TestClient, email: str, password: str = TEST_PASSWORD
) -> dict[str, str]:
    """Log in via cookie auth and return the CSRF header dict for state-changing calls."""
    resp = test_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    csrf_token = test_client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf_token
    return {CSRF_HEADER_NAME: csrf_token}
