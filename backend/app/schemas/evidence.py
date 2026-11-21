"""Pydantic v2 schemas for structured logs and engineering knowledge base."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.evidence import LogSeverity


class LogEntryIn(BaseModel):
    service: str = Field(min_length=1, max_length=120)
    environment: str = Field(default="production", min_length=1, max_length=64)
    severity: LogSeverity = LogSeverity.INFO
    timestamp: datetime | None = None
    correlation_id: str | None = Field(default=None, max_length=128)
    trace_id: str | None = Field(default=None, max_length=128)
    message: str = Field(min_length=1, max_length=8000)
    attributes: dict[str, Any] = Field(default_factory=dict)


class LogIngestRequest(BaseModel):
    entries: list[LogEntryIn] = Field(min_length=1, max_length=100)


class LogEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    service: str
    environment: str
    severity: str
    timestamp: datetime
    correlation_id: str | None
    trace_id: str | None
    message: str
    attributes_json: dict[str, Any]
    source: str
    is_synthetic: bool
    created_at: datetime


class LogIngestResponse(BaseModel):
    ingested_count: int
    is_synthetic: bool
    entries: list[LogEntryOut]


class LogSearchResponse(BaseModel):
    items: list[LogEntryOut]
    total: int
    start_time: datetime
    end_time: datetime
    has_synthetic: bool


class KnowledgeDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    created_by_user_id: int | None
    title: str
    sanitized_filename: str
    source_uri: str
    source_type: str
    mime_type: str
    version: int
    content_hash: str
    byte_size: int
    is_synthetic: bool
    indexing_status: str
    chunk_count: int
    indexing_attempts: int
    last_error: str | None
    indexed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class KnowledgeChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chunk_index: int
    section_heading: str | None
    char_start: int
    char_end: int
    token_count: int
    content: str


class KnowledgeDocumentDetailOut(KnowledgeDocumentOut):
    chunks: list[KnowledgeChunkOut] = Field(default_factory=list)


class KnowledgeDocumentListResponse(BaseModel):
    items: list[KnowledgeDocumentOut]
    total: int


class KnowledgeDocumentUploadRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    filename: str = Field(min_length=1, max_length=200)
    mime_type: str = Field(default="text/markdown", max_length=64)
    content: str | None = None
    content_base64: str | None = None
    source_uri: str | None = Field(default=None, max_length=500)
    simulate_failure: bool = False


class ReindexDocumentRequest(BaseModel):
    simulate_failure: bool = False


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)
    service_hint: str | None = Field(default=None, max_length=120)


class KnowledgeSearchHit(BaseModel):
    document_id: int
    document_title: str
    source_uri: str
    version: int
    chunk_id: int
    chunk_index: int
    section_heading: str | None
    char_start: int
    char_end: int
    lexical_score: float
    semantic_score: float
    hybrid_score: float
    snippet: str
    is_synthetic: bool
    untrusted_content: bool = True
    injection_warning: bool = False


class KnowledgeSearchResponse(BaseModel):
    query: str
    trust_boundary: str
    hits: list[KnowledgeSearchHit]


class IncidentEvidenceContextResponse(BaseModel):
    incident_id: int
    title: str
    affected_service: str | None
    environment: str
    severity: str
    window_start: datetime
    window_end: datetime
    logs: list[LogEntryOut]
    knowledge_hits: list[KnowledgeSearchHit]
    trust_boundary: str
