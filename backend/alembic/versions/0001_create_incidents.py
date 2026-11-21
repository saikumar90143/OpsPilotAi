"""Create incidents table (baseline matching the Phase 0 model).

Revision ID: 0001
Revises:
Create Date: 2026-11-20

Hand-written to match the pre-Alembic ``create_all`` schema exactly, so an
existing local SQLite database can be adopted with ``alembic stamp 0001``.
Values are frozen literals on purpose: migrations must not change if model
constants change later.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEXED_COLUMNS = ("id", "title", "service", "severity", "status", "created_at")


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("service", sa.String(length=100), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incidents")),
    )
    for column in INDEXED_COLUMNS:
        op.create_index(op.f(f"ix_incidents_{column}"), "incidents", [column])


def downgrade() -> None:
    for column in reversed(INDEXED_COLUMNS):
        op.drop_index(op.f(f"ix_incidents_{column}"), table_name="incidents")
    op.drop_table("incidents")
