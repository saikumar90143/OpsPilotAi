"""Session lifecycle and explicit transaction boundaries."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core import database
from app.models.incident import Incident
from app.models.organization import Organization
from app.models.user import User
from app.schemas.incident import IncidentCreate
from app.services import incidents as incident_service


def _count(factory: sessionmaker[Session]) -> int:
    with factory() as db:
        return db.scalar(select(func.count()).select_from(Incident)) or 0


def _seed_org_and_user(factory: sessionmaker[Session]) -> tuple[int, int]:
    with factory() as db:
        org = Organization(name="Session Test Org", slug="session-test-org")
        user = User(email="sess@test.local", full_name="Sess User", password_hash="not-used")
        db.add_all([org, user])
        db.commit()
        return org.id, user.id


def test_get_db_closes_session_after_request(
    monkeypatch: pytest.MonkeyPatch, session_factory: sessionmaker[Session]
):
    monkeypatch.setattr(database, "SessionLocal", session_factory)
    gen = database.get_db()
    db = next(gen)
    db.execute(select(1))
    assert db.in_transaction()
    with pytest.raises(StopIteration):
        next(gen)
    assert not db.in_transaction()


def test_get_db_rolls_back_uncommitted_work_on_error(
    monkeypatch: pytest.MonkeyPatch, session_factory: sessionmaker[Session]
):
    org_id, _ = _seed_org_and_user(session_factory)
    monkeypatch.setattr(database, "SessionLocal", session_factory)
    gen = database.get_db()
    db = next(gen)
    db.add(Incident(organization_id=org_id, title="Never committed", service="svc"))
    db.flush()
    with pytest.raises(RuntimeError):
        gen.throw(RuntimeError("boom"))
    assert _count(session_factory) == 0


def test_service_commit_persists_across_sessions(session_factory: sessionmaker[Session]):
    org_id, user_id = _seed_org_and_user(session_factory)
    with session_factory() as db:
        created = incident_service.create_incident(
            db,
            organization_id=org_id,
            actor_user_id=user_id,
            data=IncidentCreate(title="Persisted incident", service="svc"),
        )
    with session_factory() as other:
        assert other.get(Incident, created.id) is not None


def test_session_recovers_after_failed_flush(session_factory: sessionmaker[Session]):
    org_id, user_id = _seed_org_and_user(session_factory)
    with session_factory() as db:
        db.add(Incident(organization_id=org_id, title=None, service="svc"))  # type: ignore[arg-type]
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
        incident_service.create_incident(
            db,
            organization_id=org_id,
            actor_user_id=user_id,
            data=IncidentCreate(title="After failure", service="svc"),
        )
    assert _count(session_factory) == 1
