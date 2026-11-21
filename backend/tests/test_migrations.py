"""Alembic migrations on SQLite: upgrade from zero, backfill, downgrade, and no model drift."""

from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app.core.database import Base

BACKEND_DIR = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {
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
}


def alembic_config(database_url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.attributes["database_url"] = database_url
    return cfg


def test_single_head_revision():
    heads = ScriptDirectory.from_config(alembic_config("sqlite://")).get_heads()
    assert heads == ["0008"]


def test_upgrade_downgrade_roundtrip_and_no_drift(tmp_path: Path):
    url = f"sqlite:///{(tmp_path / 'migrations.db').as_posix()}"
    cfg = alembic_config(url)
    engine = create_engine(url)
    try:
        command.upgrade(cfg, "head")
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) == EXPECTED_TABLES

        with engine.connect() as conn:
            assert MigrationContext.configure(conn).get_current_revision() == "0008"
            assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []

        command.downgrade(cfg, "base")
        assert inspect(engine).get_table_names() == ["alembic_version"]

        command.upgrade(cfg, "head")
        assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES
    finally:
        engine.dispose()


def test_upgrade_0001_to_0002_backfills_existing_incidents(tmp_path: Path):
    url = f"sqlite:///{(tmp_path / 'backfill.db').as_posix()}"
    cfg = alembic_config(url)
    engine = create_engine(url)
    try:
        command.upgrade(cfg, "0001")
        now = datetime.now(UTC)
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO incidents (title, description, service, severity, "
                    "status, source, created_at, updated_at) "
                    "VALUES ('Pre-tenant incident', '', 'api', 'high', "
                    "'open', 'manual', :now, :now)"
                ),
                {"now": now},
            )

        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            org_id = conn.execute(text("SELECT organization_id FROM incidents")).scalar_one()
            slug = conn.execute(
                text("SELECT slug FROM organizations WHERE id = :id"), {"id": org_id}
            ).scalar_one()
            assert slug == "default"
    finally:
        engine.dispose()
