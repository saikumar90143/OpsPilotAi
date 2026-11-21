"""PostgreSQL integration tests (``@pytest.mark.postgres``).

Run against the ephemeral ``db-test`` Compose service:
    docker compose --profile test up -d db-test
    TEST_POSTGRES_URL=postgresql+psycopg://<user>:<password>@127.0.0.1:55432/opspilot_test

Each test resets the ``public`` schema, so the target database name MUST end in
``_test``; anything else is refused. Skipped (never passed) when TEST_POSTGRES_URL
is unset.
"""

from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, func, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.webhooks import get_enqueue_fn
from app.bootstrap import bootstrap_demo_data
from app.core import database
from app.core.database import Base, get_db
from app.core.secrets import SIGNATURE_HEADER, sign_webhook_payload
from app.db_check import check_database
from app.integrations.alertmanager import build_sample_alertmanager_payload
from app.main import app
from app.models.incident import Incident
from app.models.organization import Organization
from app.services import ingestion_service
from tests.conftest import TEST_PASSWORD, login_client, seed_tenants

pytestmark = pytest.mark.postgres

BACKEND_DIR = Path(__file__).resolve().parents[1]
REQUIRED_DB_SUFFIX = "_test"
MIN_SERVER_MAJOR_VERSION = 16


@pytest.fixture(scope="module")
def pg_engine(test_postgres_url: str) -> Iterator[Engine]:
    db_name = make_url(test_postgres_url).database or ""
    if not db_name.endswith(REQUIRED_DB_SUFFIX):
        pytest.fail(f"Refusing to reset database '{db_name}': name must end in '_test'.")
    engine = create_engine(test_postgres_url, connect_args={"connect_timeout": 5})
    yield engine
    engine.dispose()


@pytest.fixture()
def alembic_cfg(test_postgres_url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.attributes["database_url"] = test_postgres_url
    return cfg


def reset_schema(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))


@pytest.fixture()
def migrated(pg_engine: Engine, alembic_cfg: Config) -> Engine:
    reset_schema(pg_engine)
    command.upgrade(alembic_cfg, "head")
    return pg_engine


@pytest.fixture()
def pg_sessions(migrated: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=migrated, autoflush=False)


def test_connectivity_and_server_version(migrated: Engine):
    info = check_database(migrated)
    assert info.dialect == "postgresql"
    assert int(info.server_version.split(".")[0]) >= MIN_SERVER_MAJOR_VERSION
    assert info.alembic_revision == "0008"


def test_alembic_creates_clean_schema_from_zero(pg_engine: Engine, alembic_cfg: Config):
    reset_schema(pg_engine)
    assert inspect(pg_engine).get_table_names() == []

    command.upgrade(alembic_cfg, "head")

    inspector = inspect(pg_engine)
    assert {
        "alembic_version",
        "application_logs",
        "audit_logs",
        "external_action_connectors",
        "github_connectors",
        "inbound_events",
        "incident_affected_services",
        "incident_comments",
        "incident_evidence_refs",
        "incident_tags",
        "incident_timeline_events",
        "incidents",
        "integration_configs",
        "investigation_runs",
        "investigation_tool_calls",
        "invitations",
        "knowledge_chunks",
        "knowledge_documents",
        "memberships",
        "organizations",
        "proposed_actions",
        "refresh_tokens",
        "users",
    } == set(inspector.get_table_names())
    assert inspector.get_pk_constraint("incidents")["name"] == "pk_incidents"
    columns = {c["name"]: c for c in inspector.get_columns("incidents")}
    assert columns["created_at"]["type"].timezone is True
    assert columns["organization_id"]["nullable"] is False
    with pg_engine.connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []


def test_downgrade_and_reupgrade(migrated: Engine, alembic_cfg: Config):
    command.downgrade(alembic_cfg, "base")
    assert "incidents" not in inspect(migrated).get_table_names()
    command.upgrade(alembic_cfg, "head")
    assert "incidents" in inspect(migrated).get_table_names()


def test_timestamps_are_timezone_aware(pg_sessions: sessionmaker[Session]):
    with pg_sessions() as db:
        org = Organization(name="PG TZ Org", slug="pg-tz-org")
        db.add(org)
        db.flush()
        incident = Incident(organization_id=org.id, title="TZ check", service="svc")
        db.add(incident)
        db.commit()
        db.refresh(incident)
        assert isinstance(incident.created_at, datetime)
        assert incident.created_at.utcoffset() is not None


def test_get_db_rolls_back_on_error(
    monkeypatch: pytest.MonkeyPatch, pg_sessions: sessionmaker[Session]
):
    with pg_sessions() as db:
        org = Organization(name="PG Rollback Org", slug="pg-rb-org")
        db.add(org)
        db.commit()
        org_id = org.id

    monkeypatch.setattr(database, "SessionLocal", pg_sessions)
    gen = database.get_db()
    db = next(gen)
    db.add(Incident(organization_id=org_id, title="Rolled back", service="svc"))
    db.flush()
    with pytest.raises(RuntimeError):
        gen.throw(RuntimeError("boom"))
    with pg_sessions() as check:
        assert check.scalar(select(func.count()).select_from(Incident)) == 0


def test_postgres_tenant_isolation_rbac_and_readiness(pg_sessions: sessionmaker[Session]):
    with pg_sessions() as db:
        tenants = seed_tenants(db)

    def pg_db() -> Iterator[Session]:
        db = pg_sessions()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = pg_db
    try:
        with TestClient(app) as client:
            assert client.get("/health/ready").json()["status"] == "ready"
            assert client.get("/api/v1/incidents").status_code == 401

            a_headers = login_client(client, tenants.a_engineer.email)
            created = client.post(
                "/api/v1/incidents",
                json={"title": "PG Tenant A incident", "service": "checkout-api"},
                headers=a_headers,
            )
            assert created.status_code == 201
            a_id = created.json()["id"]
            assert created.json()["organization_id"] == tenants.org_a.id

            # Tenant B cannot list, read, update, or archive Tenant A's incident.
            b_headers = login_client(client, tenants.b_owner.email)
            assert client.get("/api/v1/incidents").json() == []
            assert client.get(f"/api/v1/incidents/{a_id}").status_code == 404
            assert (
                client.patch(
                    f"/api/v1/incidents/{a_id}/status",
                    json={"status": "resolved"},
                    headers=b_headers,
                ).status_code
                == 404
            )
            assert client.delete(f"/api/v1/incidents/{a_id}", headers=b_headers).status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_bootstrap_is_idempotent_on_postgres(pg_sessions: sessionmaker[Session]):
    with pg_sessions() as db:
        first = bootstrap_demo_data(db, demo_password=TEST_PASSWORD)
        second = bootstrap_demo_data(db, demo_password=TEST_PASSWORD)
        assert first == 5
        assert second == 0


def test_postgres_incident_lifecycle_concurrency_and_search(pg_sessions: sessionmaker[Session]):
    with pg_sessions() as db:
        tenants = seed_tenants(db)

    def pg_db() -> Iterator[Session]:
        db = pg_sessions()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = pg_db
    try:
        with TestClient(app) as client:
            a_headers = login_client(client, tenants.a_engineer.email)
            created = client.post(
                "/api/v1/incidents",
                json={
                    "title": "PG concurrency & search",
                    "service": "payments",
                    "environment": "production",
                    "severity": "critical",
                    "tags": ["pg", "latency"],
                },
                headers=a_headers,
            )
            assert created.status_code == 201
            inc_id = created.json()["id"]

            ack = client.post(
                f"/api/v1/incidents/{inc_id}/acknowledge", json={"version": 1}, headers=a_headers
            )
            assert ack.status_code == 200
            assert ack.json()["version"] == 2

            # Stale version 1 fails on PostgreSQL with 409.
            stale = client.post(
                f"/api/v1/incidents/{inc_id}/resolve", json={"version": 1}, headers=a_headers
            )
            assert stale.status_code == 409

            # Filter & search
            found = client.get(
                "/api/v1/incidents",
                params={"tag": "latency", "q": "concurrency", "sort_by": "severity"},
            )
            assert found.headers["X-Total-Count"] == "1"
            assert found.json()[0]["id"] == inc_id

            # Timeline recorded
            timeline = client.get(f"/api/v1/incidents/{inc_id}/timeline").json()
            assert [e["event_type"] for e in timeline] == [
                "incident.created",
                "incident.status_updated",
            ]
    finally:
        app.dependency_overrides.clear()


def test_postgres_webhook_ingestion_and_deduplication(pg_sessions: sessionmaker[Session]):
    import json

    with pg_sessions() as db:
        tenants = seed_tenants(db)

    def pg_db() -> Iterator[Session]:
        db = pg_sessions()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    enqueued: list[int] = []
    app.dependency_overrides[get_db] = pg_db
    app.dependency_overrides[get_enqueue_fn] = lambda: lambda ev_id, _cid: enqueued.append(ev_id)
    try:
        with TestClient(app) as client:
            a_headers = login_client(client, tenants.a_admin.email)
            cfg = client.post(
                "/api/v1/integrations",
                json={
                    "provider": "alertmanager",
                    "name": "PG Alertmanager",
                    "is_simulator_mode": False,
                },
                headers=a_headers,
            ).json()
            body = json.dumps(build_sample_alertmanager_payload()).encode("utf-8")
            sig = sign_webhook_payload(body, cfg["signing_secret"])

            r1 = client.post(
                cfg["webhook_path"],
                content=body,
                headers={"Content-Type": "application/json", SIGNATURE_HEADER: sig},
            )
            assert r1.status_code == 202 and r1.json()["duplicate"] is False

            with pg_sessions() as db:
                ingestion_service.execute_event_processing(db, event_id=enqueued[0])

            r2 = client.post(
                cfg["webhook_path"],
                content=body,
                headers={"Content-Type": "application/json", SIGNATURE_HEADER: sig},
            )
            assert r2.status_code == 202 and r2.json()["duplicate"] is True
            assert len(client.get("/api/v1/incidents").json()) == 1
    finally:
        app.dependency_overrides.clear()
