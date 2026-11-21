"""Core incident-management domain: lifecycle, concurrency, timeline, comments, evidence, tags.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("incidents", sa.Column("assignee_user_id", sa.Integer(), nullable=True))
    op.add_column("incidents", sa.Column("environment", sa.String(length=32), nullable=True))
    op.add_column(
        "incidents", sa.Column("external_source_id", sa.String(length=128), nullable=True)
    )
    op.add_column("incidents", sa.Column("fingerprint", sa.String(length=128), nullable=True))
    op.add_column("incidents", sa.Column("metadata_json", sa.JSON(), nullable=True))
    op.add_column("incidents", sa.Column("version", sa.Integer(), nullable=True))
    op.add_column(
        "incidents", sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("incidents", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("incidents", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))

    conn = op.get_bind()
    conn.execute(sa.text("UPDATE incidents SET environment = 'unknown' WHERE environment IS NULL"))
    conn.execute(sa.text("UPDATE incidents SET metadata_json = '{}' WHERE metadata_json IS NULL"))
    conn.execute(sa.text("UPDATE incidents SET version = 1 WHERE version IS NULL"))

    with op.batch_alter_table("incidents") as batch_op:
        batch_op.alter_column("environment", existing_type=sa.String(length=32), nullable=False)
        batch_op.alter_column("metadata_json", existing_type=sa.JSON(), nullable=False)
        batch_op.alter_column("version", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            op.f("fk_incidents_assignee_user_id_users"),
            "users",
            ["assignee_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(op.f("ix_incidents_assignee_user_id"), ["assignee_user_id"])
        batch_op.create_index(op.f("ix_incidents_environment"), ["environment"])
        batch_op.create_index(op.f("ix_incidents_external_source_id"), ["external_source_id"])
        batch_op.create_index(op.f("ix_incidents_fingerprint"), ["fingerprint"])

    op.create_table(
        "incident_affected_services",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("service_name", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            name=op.f("fk_incident_affected_services_incident_id_incidents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_incident_affected_services_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incident_affected_services")),
        sa.UniqueConstraint(
            "incident_id",
            "service_name",
            name=op.f("uq_incident_affected_services_incident_id"),
        ),
    )
    for col in ("id", "organization_id", "incident_id", "service_name"):
        op.create_index(
            op.f(f"ix_incident_affected_services_{col}"), "incident_affected_services", [col]
        )

    op.create_table(
        "incident_tags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("tag", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            name=op.f("fk_incident_tags_incident_id_incidents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_incident_tags_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incident_tags")),
        sa.UniqueConstraint("incident_id", "tag", name=op.f("uq_incident_tags_incident_id")),
    )
    for col in ("id", "organization_id", "incident_id", "tag"):
        op.create_index(op.f(f"ix_incident_tags_{col}"), "incident_tags", [col])

    op.create_table(
        "incident_timeline_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_incident_timeline_events_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            name=op.f("fk_incident_timeline_events_incident_id_incidents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_incident_timeline_events_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incident_timeline_events")),
    )
    for col in ("id", "organization_id", "incident_id", "event_type", "created_at"):
        op.create_index(
            op.f(f"ix_incident_timeline_events_{col}"), "incident_timeline_events", [col]
        )

    op.create_table(
        "incident_comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("author_user_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["author_user_id"],
            ["users.id"],
            name=op.f("fk_incident_comments_author_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            name=op.f("fk_incident_comments_incident_id_incidents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_incident_comments_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incident_comments")),
    )
    for col in ("id", "organization_id", "incident_id", "created_at"):
        op.create_index(op.f(f"ix_incident_comments_{col}"), "incident_comments", [col])

    op.create_table(
        "incident_evidence_refs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("added_by_user_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("uri", sa.String(length=1000), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["added_by_user_id"],
            ["users.id"],
            name=op.f("fk_incident_evidence_refs_added_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            name=op.f("fk_incident_evidence_refs_incident_id_incidents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_incident_evidence_refs_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incident_evidence_refs")),
    )
    for col in ("id", "organization_id", "incident_id", "created_at"):
        op.create_index(op.f(f"ix_incident_evidence_refs_{col}"), "incident_evidence_refs", [col])


def downgrade() -> None:
    for table, cols in (
        ("incident_evidence_refs", ("created_at", "incident_id", "organization_id", "id")),
        ("incident_comments", ("created_at", "incident_id", "organization_id", "id")),
        (
            "incident_timeline_events",
            ("created_at", "event_type", "incident_id", "organization_id", "id"),
        ),
        ("incident_tags", ("tag", "incident_id", "organization_id", "id")),
        (
            "incident_affected_services",
            ("service_name", "incident_id", "organization_id", "id"),
        ),
    ):
        for col in cols:
            op.drop_index(op.f(f"ix_{table}_{col}"), table_name=table)
        op.drop_table(table)

    with op.batch_alter_table("incidents") as batch_op:
        for col in ("fingerprint", "external_source_id", "environment", "assignee_user_id"):
            batch_op.drop_index(op.f(f"ix_incidents_{col}"))
        batch_op.drop_constraint(op.f("fk_incidents_assignee_user_id_users"), type_="foreignkey")
        for col in (
            "closed_at",
            "resolved_at",
            "acknowledged_at",
            "version",
            "metadata_json",
            "fingerprint",
            "external_source_id",
            "environment",
            "assignee_user_id",
        ):
            batch_op.drop_column(col)
