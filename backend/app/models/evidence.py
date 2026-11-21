"""Phase 7 models: structured application logs and tenant knowledge base."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

LOG_SERVICE_MAX_LENGTH = 120
LOG_ENV_MAX_LENGTH = 64
LOG_SEVERITY_MAX_LENGTH = 16
LOG_ID_MAX_LENGTH = 128
LOG_SOURCE_MAX_LENGTH = 32

KB_TITLE_MAX_LENGTH = 200
KB_FILENAME_MAX_LENGTH = 200
KB_URI_MAX_LENGTH = 500
KB_MIME_MAX_LENGTH = 64
KB_HASH_MAX_LENGTH = 64
KB_STATUS_MAX_LENGTH = 24
KB_HEADING_MAX_LENGTH = 200


class LogSeverity(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogSource(StrEnum):
    INGEST = "ingest"
    SYNTHETIC_FIXTURE = "synthetic_fixture"


class KnowledgeSourceType(StrEnum):
    UPLOAD = "upload"
    SYNTHETIC_FIXTURE = "synthetic_fixture"


class KnowledgeIndexingStatus(StrEnum):
    PENDING = "pending"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ApplicationLog(Base):
    __tablename__ = "application_logs"
    __table_args__ = (
        Index("ix_application_logs_org_ts", "organization_id", "timestamp"),
        Index("ix_application_logs_org_svc_ts", "organization_id", "service", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    service: Mapped[str] = mapped_column(String(LOG_SERVICE_MAX_LENGTH), nullable=False, index=True)
    environment: Mapped[str] = mapped_column(
        String(LOG_ENV_MAX_LENGTH), nullable=False, default="production", index=True
    )
    severity: Mapped[str] = mapped_column(
        String(LOG_SEVERITY_MAX_LENGTH), nullable=False, default=LogSeverity.INFO.value, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, index=True
    )
    correlation_id: Mapped[str | None] = mapped_column(
        String(LOG_ID_MAX_LENGTH), nullable=True, index=True
    )
    trace_id: Mapped[str | None] = mapped_column(
        String(LOG_ID_MAX_LENGTH), nullable=True, index=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    attributes_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    source: Mapped[str] = mapped_column(
        String(LOG_SOURCE_MAX_LENGTH), nullable=False, default=LogSource.INGEST.value
    )
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        UniqueConstraint("organization_id", "source_uri", "version"),
        Index("ix_knowledge_docs_org_status", "organization_id", "indexing_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(KB_TITLE_MAX_LENGTH), nullable=False)
    sanitized_filename: Mapped[str] = mapped_column(String(KB_FILENAME_MAX_LENGTH), nullable=False)
    source_uri: Mapped[str] = mapped_column(String(KB_URI_MAX_LENGTH), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(
        String(LOG_SOURCE_MAX_LENGTH), nullable=False, default=KnowledgeSourceType.UPLOAD.value
    )
    mime_type: Mapped[str] = mapped_column(String(KB_MIME_MAX_LENGTH), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content_hash: Mapped[str] = mapped_column(
        String(KB_HASH_MAX_LENGTH), nullable=False, index=True
    )
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    indexing_status: Mapped[str] = mapped_column(
        String(KB_STATUS_MAX_LENGTH),
        nullable=False,
        default=KnowledgeIndexingStatus.PENDING.value,
        index=True,
    )
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    indexing_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )

    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="KnowledgeChunk.chunk_index",
    )


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index"),
        Index("ix_knowledge_chunks_org_doc", "organization_id", "document_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section_heading: Mapped[str | None] = mapped_column(
        String(KB_HEADING_MAX_LENGTH), nullable=True
    )
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_json: Mapped[list[float]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )

    document: Mapped["KnowledgeDocument"] = relationship(back_populates="chunks")
