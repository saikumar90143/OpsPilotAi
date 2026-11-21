"""Evidence layer API routes: structured logs and tenant knowledge base."""

import base64
import binascii
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import AppSettings, DbSession, require_permission
from app.api.errors import ERROR_RESPONSES
from app.core.errors import ValidationError
from app.core.permissions import Permission
from app.models.evidence import LogSeverity
from app.schemas.evidence import (
    IncidentEvidenceContextResponse,
    KnowledgeDocumentDetailOut,
    KnowledgeDocumentListResponse,
    KnowledgeDocumentOut,
    KnowledgeDocumentUploadRequest,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    LogEntryOut,
    LogIngestRequest,
    LogIngestResponse,
    LogSearchResponse,
    ReindexDocumentRequest,
)
from app.services import evidence_service
from app.services.auth_service import AuthContext

router = APIRouter(prefix="/evidence", tags=["evidence"], responses=ERROR_RESPONSES)


@router.post(
    "/logs/ingest",
    response_model=LogIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_logs(
    payload: LogIngestRequest,
    db: DbSession,
    settings: AppSettings,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_WRITE))],
) -> LogIngestResponse:
    rows = evidence_service.ingest_logs(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        entries=payload.entries,
        settings=settings,
    )
    return LogIngestResponse(
        ingested_count=len(rows),
        is_synthetic=False,
        entries=[LogEntryOut.model_validate(r) for r in rows],
    )


@router.post(
    "/logs/load-fixtures",
    response_model=LogIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
def load_synthetic_logs(
    db: DbSession,
    settings: AppSettings,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_WRITE))],
) -> LogIngestResponse:
    rows = evidence_service.load_synthetic_logs(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        settings=settings,
    )
    return LogIngestResponse(
        ingested_count=len(rows),
        is_synthetic=True,
        entries=[LogEntryOut.model_validate(r) for r in rows],
    )


@router.get("/logs", response_model=LogSearchResponse)
def search_logs(
    db: DbSession,
    settings: AppSettings,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_READ))],
    service: str | None = Query(default=None, max_length=120),
    environment: str | None = Query(default=None, max_length=64),
    severity: LogSeverity | None = Query(default=None),
    correlation_id: str | None = Query(default=None, max_length=128),
    trace_id: str | None = Query(default=None, max_length=128),
    q: str | None = Query(default=None, max_length=200),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
) -> LogSearchResponse:
    items, total, resolved_start, resolved_end = evidence_service.search_logs(
        db,
        organization_id=auth.organization.id,
        service=service,
        environment=environment,
        severity=severity,
        correlation_id=correlation_id,
        trace_id=trace_id,
        q=q,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        settings=settings,
    )
    out_items = [LogEntryOut.model_validate(r) for r in items]
    return LogSearchResponse(
        items=out_items,
        total=total,
        start_time=resolved_start,
        end_time=resolved_end,
        has_synthetic=any(item.is_synthetic for item in out_items),
    )


@router.get(
    "/incidents/{incident_id}/context",
    response_model=IncidentEvidenceContextResponse,
)
def get_incident_context(
    incident_id: int,
    db: DbSession,
    settings: AppSettings,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_READ))],
) -> IncidentEvidenceContextResponse:
    return evidence_service.get_incident_evidence_context(
        db,
        organization_id=auth.organization.id,
        incident_id=incident_id,
        settings=settings,
    )


@router.post(
    "/kb/documents",
    response_model=KnowledgeDocumentOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_kb_document(
    payload: KnowledgeDocumentUploadRequest,
    db: DbSession,
    settings: AppSettings,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INTEGRATION_MANAGE))],
) -> KnowledgeDocumentOut:
    if payload.content_base64 is not None:
        try:
            raw_bytes = base64.b64decode(payload.content_base64, validate=True)
        except binascii.Error as exc:
            raise ValidationError("Invalid base64 payload") from exc
    elif payload.content is not None:
        raw_bytes = payload.content.encode("utf-8")
    else:
        raise ValidationError("Either 'content' or 'content_base64' must be provided")

    doc = evidence_service.upload_knowledge_document(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        title=payload.title,
        filename=payload.filename,
        mime_type=payload.mime_type,
        raw_bytes=raw_bytes,
        source_uri=payload.source_uri,
        simulate_failure=payload.simulate_failure,
        settings=settings,
    )
    return KnowledgeDocumentOut.model_validate(doc)


@router.post(
    "/kb/load-fixtures",
    response_model=KnowledgeDocumentListResponse,
    status_code=status.HTTP_201_CREATED,
)
def load_synthetic_runbooks(
    db: DbSession,
    settings: AppSettings,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INTEGRATION_MANAGE))],
) -> KnowledgeDocumentListResponse:
    docs = evidence_service.load_synthetic_runbooks(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        settings=settings,
    )
    return KnowledgeDocumentListResponse(
        items=[KnowledgeDocumentOut.model_validate(d) for d in docs],
        total=len(docs),
    )


@router.get("/kb/documents", response_model=KnowledgeDocumentListResponse)
def list_kb_documents(
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_READ))],
) -> KnowledgeDocumentListResponse:
    docs = evidence_service.list_knowledge_documents(db, organization_id=auth.organization.id)
    return KnowledgeDocumentListResponse(
        items=[KnowledgeDocumentOut.model_validate(d) for d in docs],
        total=len(docs),
    )


@router.get("/kb/documents/{doc_id}", response_model=KnowledgeDocumentDetailOut)
def get_kb_document(
    doc_id: int,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_READ))],
) -> KnowledgeDocumentDetailOut:
    doc = evidence_service.get_knowledge_document(
        db, organization_id=auth.organization.id, doc_id=doc_id
    )
    return KnowledgeDocumentDetailOut.model_validate(doc)


@router.post("/kb/documents/{doc_id}/reindex", response_model=KnowledgeDocumentOut)
def reindex_kb_document(
    doc_id: int,
    db: DbSession,
    settings: AppSettings,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INTEGRATION_MANAGE))],
    payload: ReindexDocumentRequest | None = None,
) -> KnowledgeDocumentOut:
    doc = evidence_service.reindex_knowledge_document(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        doc_id=doc_id,
        simulate_failure=payload.simulate_failure if payload else False,
        settings=settings,
    )
    return KnowledgeDocumentOut.model_validate(doc)


@router.delete("/kb/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_kb_document(
    doc_id: int,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INTEGRATION_MANAGE))],
) -> None:
    evidence_service.delete_knowledge_document(
        db,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        doc_id=doc_id,
    )


@router.post("/kb/search", response_model=KnowledgeSearchResponse)
def search_kb(
    payload: KnowledgeSearchRequest,
    db: DbSession,
    auth: Annotated[AuthContext, Depends(require_permission(Permission.INCIDENT_READ))],
) -> KnowledgeSearchResponse:
    return evidence_service.search_knowledge_base(
        db,
        organization_id=auth.organization.id,
        query=payload.query,
        limit=payload.limit,
        service_hint=payload.service_hint,
    )
