"""Multi-tenant identity, RBAC, refresh tokens, invitations, and audit logs.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-21
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
    )
    op.create_index(op.f("ix_organizations_id"), "organizations", ["id"])
    op.create_index(op.f("ix_organizations_slug"), "organizations", ["slug"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(op.f("ix_users_id"), "users", ["id"])
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "memberships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_memberships_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_memberships_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memberships")),
        sa.UniqueConstraint(
            "organization_id", "user_id", name=op.f("uq_memberships_organization_id")
        ),
    )
    op.create_index(op.f("ix_memberships_id"), "memberships", ["id"])
    op.create_index(op.f("ix_memberships_organization_id"), "memberships", ["organization_id"])
    op.create_index(op.f("ix_memberships_user_id"), "memberships", ["user_id"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("family_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_refresh_tokens_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["replaced_by_id"],
            ["refresh_tokens.id"],
            name=op.f("fk_refresh_tokens_replaced_by_id_refresh_tokens"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
    )
    op.create_index(op.f("ix_refresh_tokens_id"), "refresh_tokens", ["id"])
    op.create_index(
        op.f("ix_refresh_tokens_token_hash"), "refresh_tokens", ["token_hash"], unique=True
    )
    op.create_index(op.f("ix_refresh_tokens_family_id"), "refresh_tokens", ["family_id"])
    op.create_index(op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"])
    op.create_index(
        op.f("ix_refresh_tokens_organization_id"), "refresh_tokens", ["organization_id"]
    )

    op.create_table(
        "invitations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("invited_by_user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["invited_by_user_id"],
            ["users.id"],
            name=op.f("fk_invitations_invited_by_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_invitations_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invitations")),
    )
    op.create_index(op.f("ix_invitations_id"), "invitations", ["id"])
    op.create_index(op.f("ix_invitations_organization_id"), "invitations", ["organization_id"])
    op.create_index(op.f("ix_invitations_email"), "invitations", ["email"])
    op.create_index(op.f("ix_invitations_token_hash"), "invitations", ["token_hash"], unique=True)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=True),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_audit_logs_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_audit_logs_organization_id_organizations"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index(op.f("ix_audit_logs_id"), "audit_logs", ["id"])
    op.create_index(op.f("ix_audit_logs_organization_id"), "audit_logs", ["organization_id"])
    op.create_index(op.f("ix_audit_logs_actor_user_id"), "audit_logs", ["actor_user_id"])
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"])
    op.create_index(op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"])

    # Add tenant-ownership & soft-delete columns to incidents.
    op.add_column("incidents", sa.Column("organization_id", sa.Integer(), nullable=True))
    op.add_column("incidents", sa.Column("created_by_user_id", sa.Integer(), nullable=True))
    op.add_column("incidents", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))

    conn = op.get_bind()
    incident_count = conn.execute(sa.text("SELECT COUNT(*) FROM incidents")).scalar_one()
    if incident_count > 0:
        now = datetime.now(UTC)
        conn.execute(
            sa.text(
                "INSERT INTO organizations (name, slug, created_at, updated_at) "
                "VALUES (:name, :slug, :created_at, :updated_at)"
            ),
            {
                "name": "Default Organization",
                "slug": "default",
                "created_at": now,
                "updated_at": now,
            },
        )
        default_org_id = conn.execute(
            sa.text("SELECT id FROM organizations WHERE slug = 'default'")
        ).scalar_one()
        conn.execute(
            sa.text("UPDATE incidents SET organization_id = :org_id WHERE organization_id IS NULL"),
            {"org_id": default_org_id},
        )

    with op.batch_alter_table("incidents") as batch_op:
        batch_op.alter_column("organization_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            op.f("fk_incidents_organization_id_organizations"),
            "organizations",
            ["organization_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            op.f("fk_incidents_created_by_user_id_users"),
            "users",
            ["created_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(op.f("ix_incidents_organization_id"), ["organization_id"])
        batch_op.create_index(op.f("ix_incidents_archived_at"), ["archived_at"])


def downgrade() -> None:
    with op.batch_alter_table("incidents") as batch_op:
        batch_op.drop_index(op.f("ix_incidents_archived_at"))
        batch_op.drop_index(op.f("ix_incidents_organization_id"))
        batch_op.drop_constraint(op.f("fk_incidents_created_by_user_id_users"), type_="foreignkey")
        batch_op.drop_constraint(
            op.f("fk_incidents_organization_id_organizations"), type_="foreignkey"
        )
        batch_op.drop_column("archived_at")
        batch_op.drop_column("created_by_user_id")
        batch_op.drop_column("organization_id")

    for index_name in (
        "ix_audit_logs_created_at",
        "ix_audit_logs_action",
        "ix_audit_logs_actor_user_id",
        "ix_audit_logs_organization_id",
        "ix_audit_logs_id",
    ):
        op.drop_index(op.f(index_name), table_name="audit_logs")
    op.drop_table("audit_logs")

    for index_name in (
        "ix_invitations_token_hash",
        "ix_invitations_email",
        "ix_invitations_organization_id",
        "ix_invitations_id",
    ):
        op.drop_index(op.f(index_name), table_name="invitations")
    op.drop_table("invitations")

    for index_name in (
        "ix_refresh_tokens_organization_id",
        "ix_refresh_tokens_user_id",
        "ix_refresh_tokens_family_id",
        "ix_refresh_tokens_token_hash",
        "ix_refresh_tokens_id",
    ):
        op.drop_index(op.f(index_name), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    for index_name in (
        "ix_memberships_user_id",
        "ix_memberships_organization_id",
        "ix_memberships_id",
    ):
        op.drop_index(op.f(index_name), table_name="memberships")
    op.drop_table("memberships")

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_table("users")

    op.drop_index(op.f("ix_organizations_slug"), table_name="organizations")
    op.drop_index(op.f("ix_organizations_id"), table_name="organizations")
    op.drop_table("organizations")
