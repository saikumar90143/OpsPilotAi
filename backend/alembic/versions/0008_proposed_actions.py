"""External action connectors and human-gated proposed actions tables.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_action_connectors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("base_url", sa.String(length=300), nullable=True),
        sa.Column("allowed_targets_json", sa.JSON(), nullable=False),
        sa.Column("encrypted_credential", sa.Text(), nullable=True),
        sa.Column("permission_summary_json", sa.JSON(), nullable=False),
        sa.Column("last_test_status", sa.String(length=24), nullable=False),
        sa.Column("last_test_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "provider", "name"),
    )
    op.create_index(
        op.f("ix_external_action_connectors_id"),
        "external_action_connectors",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_external_action_connectors_organization_id"),
        "external_action_connectors",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_external_action_connectors_provider"),
        "external_action_connectors",
        ["provider"],
        unique=False,
    )

    op.create_table(
        "proposed_actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("investigation_id", sa.Integer(), nullable=True),
        sa.Column("connector_id", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(length=48), nullable=False),
        sa.Column("target_system", sa.String(length=24), nullable=False),
        sa.Column("target_destination", sa.String(length=120), nullable=False),
        sa.Column("payload_preview_json", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("evidence_links_json", sa.JSON(), nullable=False),
        sa.Column("requested_by_type", sa.String(length=16), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("approved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_by_user_id", sa.Integer(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("execution_attempts", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=True),
        sa.Column("external_url", sa.String(length=500), nullable=True),
        sa.Column("execution_result_json", sa.JSON(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("audit_metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["connector_id"], ["external_action_connectors.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["investigation_id"], ["investigation_runs.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rejected_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "idempotency_key"),
    )
    op.create_index(op.f("ix_proposed_actions_id"), "proposed_actions", ["id"], unique=False)
    op.create_index(
        op.f("ix_proposed_actions_organization_id"),
        "proposed_actions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_proposed_actions_incident_id"),
        "proposed_actions",
        ["incident_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_proposed_actions_status"), "proposed_actions", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_proposed_actions_created_at"),
        "proposed_actions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_proposed_actions_org_status",
        "proposed_actions",
        ["organization_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_proposed_actions_org_inc",
        "proposed_actions",
        ["organization_id", "incident_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_proposed_actions_org_inc", table_name="proposed_actions")
    op.drop_index("ix_proposed_actions_org_status", table_name="proposed_actions")
    op.drop_index(op.f("ix_proposed_actions_created_at"), table_name="proposed_actions")
    op.drop_index(op.f("ix_proposed_actions_status"), table_name="proposed_actions")
    op.drop_index(op.f("ix_proposed_actions_incident_id"), table_name="proposed_actions")
    op.drop_index(op.f("ix_proposed_actions_organization_id"), table_name="proposed_actions")
    op.drop_index(op.f("ix_proposed_actions_id"), table_name="proposed_actions")
    op.drop_table("proposed_actions")

    op.drop_index(
        op.f("ix_external_action_connectors_provider"),
        table_name="external_action_connectors",
    )
    op.drop_index(
        op.f("ix_external_action_connectors_organization_id"),
        table_name="external_action_connectors",
    )
    op.drop_index(op.f("ix_external_action_connectors_id"), table_name="external_action_connectors")
    op.drop_table("external_action_connectors")
