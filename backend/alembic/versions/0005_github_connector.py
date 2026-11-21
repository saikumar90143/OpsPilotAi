"""Read-only GitHub connector configuration table.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "github_connectors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("auth_type", sa.String(length=24), nullable=False),
        sa.Column("github_app_id", sa.String(length=64), nullable=True),
        sa.Column("github_installation_id", sa.String(length=64), nullable=True),
        sa.Column("encrypted_credential", sa.Text(), nullable=True),
        sa.Column("encrypted_webhook_secret", sa.Text(), nullable=True),
        sa.Column("webhook_endpoint_token", sa.String(length=64), nullable=False),
        sa.Column("service_repo_map_json", sa.JSON(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("last_test_status", sa.String(length=24), nullable=False),
        sa.Column("last_test_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("permission_summary_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_github_connectors_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_github_connectors")),
    )
    for col in ("id", "organization_id"):
        op.create_index(op.f(f"ix_github_connectors_{col}"), "github_connectors", [col])
    op.create_index(
        op.f("ix_github_connectors_webhook_endpoint_token"),
        "github_connectors",
        ["webhook_endpoint_token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_github_connectors_webhook_endpoint_token"), table_name="github_connectors"
    )
    for col in ("organization_id", "id"):
        op.drop_index(op.f(f"ix_github_connectors_{col}"), table_name="github_connectors")
    op.drop_table("github_connectors")
