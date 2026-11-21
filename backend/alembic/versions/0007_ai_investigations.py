"""AI investigation runs and tool calls tables.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "investigation_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("provider_mode", sa.String(length=24), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("window_hours", sa.Integer(), nullable=False),
        sa.Column("graph_steps", sa.Integer(), nullable=False),
        sa.Column("tool_calls_count", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("evidence_bundle_json", sa.JSON(), nullable=False),
        sa.Column("report_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("human_feedback_rating", sa.String(length=24), nullable=True),
        sa.Column("human_feedback_note", sa.Text(), nullable=True),
        sa.Column("feedback_by_user_id", sa.Integer(), nullable=True),
        sa.Column("feedback_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["feedback_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_investigation_runs_id"), "investigation_runs", ["id"], unique=False)
    op.create_index(
        op.f("ix_investigation_runs_organization_id"),
        "investigation_runs",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_investigation_runs_incident_id"),
        "investigation_runs",
        ["incident_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_investigation_runs_status"), "investigation_runs", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_investigation_runs_created_at"),
        "investigation_runs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_investigation_runs_org_inc",
        "investigation_runs",
        ["organization_id", "incident_id"],
        unique=False,
    )
    op.create_index(
        "ix_investigation_runs_org_created",
        "investigation_runs",
        ["organization_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "investigation_tool_calls",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("investigation_id", sa.Integer(), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("input_summary_json", sa.JSON(), nullable=False),
        sa.Column("output_count", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["investigation_id"], ["investigation_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_investigation_tool_calls_id"), "investigation_tool_calls", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_investigation_tool_calls_organization_id"),
        "investigation_tool_calls",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_investigation_tool_calls_investigation_id"),
        "investigation_tool_calls",
        ["investigation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_investigation_tool_calls_investigation_id"),
        table_name="investigation_tool_calls",
    )
    op.drop_index(
        op.f("ix_investigation_tool_calls_organization_id"),
        table_name="investigation_tool_calls",
    )
    op.drop_index(op.f("ix_investigation_tool_calls_id"), table_name="investigation_tool_calls")
    op.drop_table("investigation_tool_calls")

    op.drop_index("ix_investigation_runs_org_created", table_name="investigation_runs")
    op.drop_index("ix_investigation_runs_org_inc", table_name="investigation_runs")
    op.drop_index(op.f("ix_investigation_runs_created_at"), table_name="investigation_runs")
    op.drop_index(op.f("ix_investigation_runs_status"), table_name="investigation_runs")
    op.drop_index(op.f("ix_investigation_runs_incident_id"), table_name="investigation_runs")
    op.drop_index(op.f("ix_investigation_runs_organization_id"), table_name="investigation_runs")
    op.drop_index(op.f("ix_investigation_runs_id"), table_name="investigation_runs")
    op.drop_table("investigation_runs")
