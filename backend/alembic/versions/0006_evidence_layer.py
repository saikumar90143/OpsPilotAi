"""Evidence layer tables: application_logs, knowledge_documents, knowledge_chunks.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "application_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("service", sa.String(length=120), nullable=False),
        sa.Column("environment", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
        sa.Column("trace_id", sa.String(length=128), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("attributes_json", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_application_logs_id"), "application_logs", ["id"], unique=False)
    op.create_index(
        op.f("ix_application_logs_organization_id"),
        "application_logs",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_application_logs_service"), "application_logs", ["service"], unique=False
    )
    op.create_index(
        op.f("ix_application_logs_environment"),
        "application_logs",
        ["environment"],
        unique=False,
    )
    op.create_index(
        op.f("ix_application_logs_severity"), "application_logs", ["severity"], unique=False
    )
    op.create_index(
        op.f("ix_application_logs_timestamp"), "application_logs", ["timestamp"], unique=False
    )
    op.create_index(
        op.f("ix_application_logs_correlation_id"),
        "application_logs",
        ["correlation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_application_logs_trace_id"), "application_logs", ["trace_id"], unique=False
    )
    op.create_index(
        "ix_application_logs_org_ts",
        "application_logs",
        ["organization_id", "timestamp"],
        unique=False,
    )
    op.create_index(
        "ix_application_logs_org_svc_ts",
        "application_logs",
        ["organization_id", "service", "timestamp"],
        unique=False,
    )

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("sanitized_filename", sa.String(length=200), nullable=False),
        sa.Column("source_uri", sa.String(length=500), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("indexing_status", sa.String(length=24), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("indexing_attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "source_uri", "version"),
    )
    op.create_index(op.f("ix_knowledge_documents_id"), "knowledge_documents", ["id"], unique=False)
    op.create_index(
        op.f("ix_knowledge_documents_organization_id"),
        "knowledge_documents",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_documents_source_uri"),
        "knowledge_documents",
        ["source_uri"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_documents_content_hash"),
        "knowledge_documents",
        ["content_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_documents_indexing_status"),
        "knowledge_documents",
        ["indexing_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_documents_created_at"),
        "knowledge_documents",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_docs_org_status",
        "knowledge_documents",
        ["organization_id", "indexing_status"],
        unique=False,
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("section_heading", sa.String(length=200), nullable=True),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "chunk_index"),
    )
    op.create_index(op.f("ix_knowledge_chunks_id"), "knowledge_chunks", ["id"], unique=False)
    op.create_index(
        op.f("ix_knowledge_chunks_organization_id"),
        "knowledge_chunks",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_chunks_document_id"),
        "knowledge_chunks",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_chunks_org_doc",
        "knowledge_chunks",
        ["organization_id", "document_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_chunks_org_doc", table_name="knowledge_chunks")
    op.drop_index(op.f("ix_knowledge_chunks_document_id"), table_name="knowledge_chunks")
    op.drop_index(op.f("ix_knowledge_chunks_organization_id"), table_name="knowledge_chunks")
    op.drop_index(op.f("ix_knowledge_chunks_id"), table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")

    op.drop_index("ix_knowledge_docs_org_status", table_name="knowledge_documents")
    op.drop_index(op.f("ix_knowledge_documents_created_at"), table_name="knowledge_documents")
    op.drop_index(op.f("ix_knowledge_documents_indexing_status"), table_name="knowledge_documents")
    op.drop_index(op.f("ix_knowledge_documents_content_hash"), table_name="knowledge_documents")
    op.drop_index(op.f("ix_knowledge_documents_source_uri"), table_name="knowledge_documents")
    op.drop_index(op.f("ix_knowledge_documents_organization_id"), table_name="knowledge_documents")
    op.drop_index(op.f("ix_knowledge_documents_id"), table_name="knowledge_documents")
    op.drop_table("knowledge_documents")

    op.drop_index("ix_application_logs_org_svc_ts", table_name="application_logs")
    op.drop_index("ix_application_logs_org_ts", table_name="application_logs")
    op.drop_index(op.f("ix_application_logs_trace_id"), table_name="application_logs")
    op.drop_index(op.f("ix_application_logs_correlation_id"), table_name="application_logs")
    op.drop_index(op.f("ix_application_logs_timestamp"), table_name="application_logs")
    op.drop_index(op.f("ix_application_logs_severity"), table_name="application_logs")
    op.drop_index(op.f("ix_application_logs_environment"), table_name="application_logs")
    op.drop_index(op.f("ix_application_logs_service"), table_name="application_logs")
    op.drop_index(op.f("ix_application_logs_organization_id"), table_name="application_logs")
    op.drop_index(op.f("ix_application_logs_id"), table_name="application_logs")
    op.drop_table("application_logs")
