"""Append-only audit trail and secret-leakage checks."""

import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.audit_log import AuditLog
from app.repositories import audit_repo
from tests.conftest import TEST_PASSWORD, SeededTenants, login_client


def test_auth_and_privileged_actions_recorded_without_secrets(
    client: TestClient,
    tenants: SeededTenants,
    session_factory: sessionmaker[Session],
    caplog: pytest.LogCaptureFixture,
):
    caplog.set_level(logging.INFO)

    # Failed login + successful login + incident create + logout
    client.post(
        "/api/v1/auth/login", json={"email": tenants.a_owner.email, "password": "WrongPassword!"}
    )
    headers = login_client(client, tenants.a_owner.email)
    inc = client.post(
        "/api/v1/incidents", json={"title": "Audited incident", "service": "api"}, headers=headers
    )
    assert inc.status_code == 201
    client.post("/api/v1/auth/logout", headers=headers)

    # Verify audit records exist and contain no passwords or tokens.
    with session_factory() as db:
        entries = list(db.scalars(select(AuditLog).order_by(AuditLog.id.asc())).all())
    actions = [e.action for e in entries]
    assert "auth.login.failure" in actions
    assert "auth.login.success" in actions
    assert "incident.created" in actions
    assert "auth.logout" in actions

    serialized = " ".join(str(e.metadata_json) for e in entries)
    assert TEST_PASSWORD not in serialized
    assert "WrongPassword!" not in serialized
    assert tenants.a_owner.password_hash not in serialized
    assert TEST_PASSWORD not in caplog.text
    assert "WrongPassword!" not in caplog.text


def test_audit_repo_sanitizes_sensitive_metadata_keys(
    session_factory: sessionmaker[Session], tenants: SeededTenants
):
    with session_factory() as db:
        entry = audit_repo.append_event(
            db,
            action="test.sanitize",
            organization_id=tenants.org_a.id,
            metadata={
                "password": "secret-password",
                "refresh_token": "raw-refresh",
                "db_url": "postgresql+psycopg://u:secret-db-pw@db:5432/opspilot",
                "safe_key": "ok",
            },
        )
        db.commit()
        db.refresh(entry)
        assert entry.metadata_json["password"] == "***"
        assert entry.metadata_json["refresh_token"] == "***"
        assert "secret-db-pw" not in entry.metadata_json["db_url"]
        assert entry.metadata_json["safe_key"] == "ok"
