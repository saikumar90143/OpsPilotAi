"""Event ingestion pipeline: integration_configs and inbound_events tables.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integration_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("is_simulator_mode", sa.Boolean(), nullable=False),
        sa.Column("webhook_endpoint_token", sa.String(length=64), nullable=False),
        sa.Column("encrypted_signing_secret", sa.Text(), nullable=False),
        sa.Column("previous_encrypted_signing_secret", sa.Text(), nullable=True),
        sa.Column("secret_rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotation_grace_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_integration_configs_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_integration_configs")),
    )
    for col in ("id", "organization_id", "provider"):
        op.create_index(op.f(f"ix_integration_configs_{col}"), "integration_configs", [col])
    op.create_index(
        op.f("ix_integration_configs_webhook_endpoint_token"),
        "integration_configs",
        ["webhook_endpoint_token"],
        unique=True,
    )

    op.create_table(
        "inbound_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("integration_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("provider_event_id", sa.String(length=128), nullable=False),
        sa.Column("fingerprint", sa.String(length=128), nullable=False),
        sa.Column("is_simulated", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=True),
        sa.Column("raw_payload_json", sa.JSON(), nullable=False),
        sa.Column("normalized_payload_json", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            name=op.f("fk_inbound_events_incident_id_incidents"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["integration_id"],
            ["integration_configs.id"],
            name=op.f("fk_inbound_events_integration_id_integration_configs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_inbound_events_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inbound_events")),
        sa.UniqueConstraint(
            "organization_id",
            "provider",
            "idempotency_key",
            name=op.f("uq_inbound_events_organization_id"),
        ),
    )
    for col in (
        "id",
        "organization_id",
        "integration_id",
        "provider",
        "provider_event_id",
        "fingerprint",
        "is_simulated",
        "status",
        "incident_id",
        "received_at",
    ):
        op.create_index(op.f(f"ix_inbound_events_{col}"), "inbound_events", [col])


def downgrade() -> None:
    for col in (
        "received_at",
        "incident_id",
        "status",
        "is_simulated",
        "fingerprint",
        "provider_event_id",
        "provider",
        "integration_id",
        "organization_id",
        "id",
    ):
        op.drop_index(op.f(f"ix_inbound_events_{col}"), table_name="inbound_events")
    op.drop_table("inbound_events")

    op.drop_index(
        op.f("ix_integration_configs_webhook_endpoint_token"), table_name="integration_configs"
    )
    for col in ("provider", "organization_id", "id"):
        op.drop_index(op.f(f"ix_integration_configs_{col}"), table_name="integration_configs")
    op.drop_table("integration_configs")
