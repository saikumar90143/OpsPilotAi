"""Fixed allowlist of typed, read-only, tenant-scoped, time-bounded investigation tools."""

import time
from collections.abc import Callable
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.redaction import redact_text, redact_value
from app.models.github_connector import GitHubConnector
from app.models.incident import Incident
from app.models.incident_details import EvidenceKind, IncidentEvidenceRef
from app.models.investigation import InvestigationToolStatus
from app.schemas.investigation import EvidenceBundleItem
from app.services import evidence_service, github_service

ALLOWED_TOOL_NAMES = frozenset(
    {
        "get_incident_history",
        "search_service_logs",
        "correlate_github_evidence",
        "search_knowledge_base",
    }
)


@dataclass(frozen=True)
class ToolExecutionRecord:
    step_number: int
    tool_name: str
    status: InvestigationToolStatus
    input_summary: dict[str, Any]
    items: list[EvidenceBundleItem]
    latency_ms: int
    error_message: str | None = None


def _run_with_timeout(
    fn: Callable[[], list[EvidenceBundleItem]], timeout_s: float
) -> list[EvidenceBundleItem]:
    # Execute on the owning Session thread (SQLAlchemy Sessions are not thread-safe)
    # and enforce the configured timeout budget.
    started = time.perf_counter()
    result = fn()
    if (time.perf_counter() - started) > timeout_s:
        raise FuturesTimeoutError(f"Tool exceeded {timeout_s}s budget")
    return result


def _tool_get_incident_history(
    db: Session, *, organization_id: int, incident: Incident, window_start: datetime
) -> list[EvidenceBundleItem]:
    items: list[EvidenceBundleItem] = [
        EvidenceBundleItem(
            evidence_id=f"EV-INC-{incident.id}",
            source_type="incident",
            title=redact_text(incident.title),
            timestamp=incident.created_at.isoformat(),
            url_or_uri=f"/incidents/{incident.id}",
            summary=redact_text(
                f"Service={incident.service}, env={incident.environment}, "
                f"severity={incident.severity}, status={incident.status}. "
                f"{incident.description[:300]}"
            ),
            is_synthetic=False,
            untrusted_content=True,
            metadata={"service": incident.service, "severity": incident.severity},
        )
    ]
    related = list(
        db.scalars(
            select(Incident)
            .where(
                Incident.organization_id == organization_id,
                Incident.service == incident.service,
                Incident.id != incident.id,
                Incident.created_at >= window_start,
                Incident.archived_at.is_(None),
            )
            .order_by(Incident.created_at.desc())
            .limit(3)
        ).all()
    )
    for rel in related:
        items.append(
            EvidenceBundleItem(
                evidence_id=f"EV-INC-{rel.id}",
                source_type="incident",
                title=redact_text(f"Related incident #{rel.id}: {rel.title}"),
                timestamp=rel.created_at.isoformat(),
                url_or_uri=f"/incidents/{rel.id}",
                summary=redact_text(
                    f"Status={rel.status}, severity={rel.severity}, service={rel.service}"
                ),
                is_synthetic=False,
                untrusted_content=True,
                metadata={"related": True},
            )
        )
    return items


def _tool_search_service_logs(
    db: Session,
    *,
    organization_id: int,
    incident: Incident,
    window_start: datetime,
    window_end: datetime,
    settings: Settings,
) -> list[EvidenceBundleItem]:
    logs, _, _, _ = evidence_service.search_logs(
        db,
        organization_id=organization_id,
        service=incident.service,
        start_time=window_start,
        end_time=window_end,
        limit=10,
        settings=settings,
    )
    items: list[EvidenceBundleItem] = []
    for row in logs:
        items.append(
            EvidenceBundleItem(
                evidence_id=f"EV-LOG-{row.id}",
                source_type="log",
                title=f"[{row.severity}] {row.service} ({row.environment})",
                timestamp=row.timestamp.isoformat(),
                url_or_uri=f"/evidence?service={row.service}",
                summary=redact_text(row.message[:400]),
                is_synthetic=row.is_synthetic,
                untrusted_content=True,
                metadata=redact_value(
                    {
                        "severity": row.severity,
                        "trace_id": row.trace_id,
                        "correlation_id": row.correlation_id,
                    }
                ),
            )
        )
    return items


def _tool_correlate_github_evidence(
    db: Session,
    *,
    organization_id: int,
    incident: Incident,
    settings: Settings,
) -> list[EvidenceBundleItem]:
    refs = list(
        db.scalars(
            select(IncidentEvidenceRef)
            .where(
                IncidentEvidenceRef.organization_id == organization_id,
                IncidentEvidenceRef.incident_id == incident.id,
                IncidentEvidenceRef.kind == EvidenceKind.COMMIT.value,
            )
            .order_by(IncidentEvidenceRef.created_at.desc())
            .limit(5)
        ).all()
    )
    if not refs:
        connector = db.scalar(
            select(GitHubConnector).where(
                GitHubConnector.organization_id == organization_id,
                GitHubConnector.mode == "mock",
            )
        )
        if connector is not None:
            # Read-only mock correlation in memory without mutating incident evidence refs
            adapter = github_service.build_provider(connector, settings)
            repo_full = connector.service_repo_map_json.get(incident.service)
            if repo_full and "/" in repo_full:
                owner, repo_name = repo_full.split("/", 1)
                until = datetime.now(UTC)
                since = until - timedelta(hours=settings.github_correlation_lookback_hours)
                commits = adapter.list_commits(
                    owner=owner, repo=repo_name, since=since, until=until, per_page=3
                ).items
                return [
                    EvidenceBundleItem(
                        evidence_id=f"EV-GH-{c.sha[:7]}",
                        source_type="github",
                        title=redact_text(f"Commit {c.sha[:7]}: {c.message.splitlines()[0][:120]}"),
                        timestamp=c.committed_at.isoformat(),
                        url_or_uri=c.html_url,
                        summary=redact_text(f"Author={c.author} on {repo_full}"),
                        is_synthetic=True,
                        untrusted_content=True,
                        metadata={"repo": repo_full, "sha": c.sha[:7]},
                    )
                    for c in commits
                ]
    return [
        EvidenceBundleItem(
            evidence_id=f"EV-GH-{r.id}",
            source_type="github",
            title=redact_text(r.title[:160]),
            timestamp=r.created_at.isoformat(),
            url_or_uri=r.uri,
            summary=redact_text((r.summary or "")[:300]),
            is_synthetic=bool(r.metadata_json.get("mode") == "mock"),
            untrusted_content=True,
            metadata=redact_value(r.metadata_json),
        )
        for r in refs
    ]


def _tool_search_knowledge_base(
    db: Session, *, organization_id: int, incident: Incident
) -> list[EvidenceBundleItem]:
    res = evidence_service.search_knowledge_base(
        db,
        organization_id=organization_id,
        query=incident.title,
        limit=4,
        service_hint=incident.service,
    )
    return [
        EvidenceBundleItem(
            evidence_id=f"EV-KB-{hit.chunk_id}",
            source_type="knowledge_base",
            title=redact_text(f"{hit.document_title} (v{hit.version})"),
            timestamp=None,
            url_or_uri=hit.source_uri,
            summary=redact_text(hit.snippet[:350]),
            is_synthetic=hit.is_synthetic,
            untrusted_content=True,
            metadata={
                "section_heading": hit.section_heading,
                "hybrid_score": hit.hybrid_score,
                "injection_warning": hit.injection_warning,
            },
        )
        for hit in res.hits
    ]


def execute_allowlisted_tool(
    tool_name: str,
    *,
    step_number: int,
    db: Session,
    organization_id: int,
    incident: Incident,
    window_start: datetime,
    window_end: datetime,
    settings: Settings,
    simulate_timeout: bool = False,
) -> ToolExecutionRecord:
    """Execute one approved read-only tool with timeout, redaction, and safe error mapping."""
    if tool_name not in ALLOWED_TOOL_NAMES:
        return ToolExecutionRecord(
            step_number=step_number,
            tool_name=tool_name,
            status=InvestigationToolStatus.ERROR,
            input_summary={"incident_id": incident.id},
            items=[],
            latency_ms=0,
            error_message=f"Tool '{tool_name}' is not in the read-only allowlist",
        )

    started = time.perf_counter()
    input_summary = {
        "incident_id": incident.id,
        "service": incident.service,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
    }

    def _dispatch() -> list[EvidenceBundleItem]:
        if simulate_timeout:
            raise FuturesTimeoutError("Simulated tool timeout")
        if tool_name == "get_incident_history":
            return _tool_get_incident_history(
                db, organization_id=organization_id, incident=incident, window_start=window_start
            )
        if tool_name == "search_service_logs":
            return _tool_search_service_logs(
                db,
                organization_id=organization_id,
                incident=incident,
                window_start=window_start,
                window_end=window_end,
                settings=settings,
            )
        if tool_name == "correlate_github_evidence":
            return _tool_correlate_github_evidence(
                db, organization_id=organization_id, incident=incident, settings=settings
            )
        return _tool_search_knowledge_base(db, organization_id=organization_id, incident=incident)

    try:
        items = _run_with_timeout(_dispatch, settings.ai_tool_timeout_seconds)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return ToolExecutionRecord(
            step_number=step_number,
            tool_name=tool_name,
            status=InvestigationToolStatus.SUCCESS,
            input_summary=input_summary,
            items=items,
            latency_ms=elapsed_ms,
        )
    except FuturesTimeoutError:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return ToolExecutionRecord(
            step_number=step_number,
            tool_name=tool_name,
            status=InvestigationToolStatus.TIMEOUT,
            input_summary=input_summary,
            items=[],
            latency_ms=elapsed_ms,
            error_message=f"Tool timed out after {settings.ai_tool_timeout_seconds}s",
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return ToolExecutionRecord(
            step_number=step_number,
            tool_name=tool_name,
            status=InvestigationToolStatus.ERROR,
            input_summary=input_summary,
            items=[],
            latency_ms=elapsed_ms,
            error_message=redact_text(f"{type(exc).__name__}: {exc}")[:300],
        )
