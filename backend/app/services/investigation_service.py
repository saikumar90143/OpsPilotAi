"""Domain service for read-only AI investigation runs, quotas, cancellation, and feedback."""

import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.ai.graph import run_investigation_graph
from app.ai.model_client import InvestigationModelClient, build_model_client
from app.core.config import Settings, get_settings
from app.core.errors import ConflictError, NotFoundError, RateLimitedError
from app.core.telemetry import (
    AI_INVESTIGATION_DURATION_SECONDS,
    AI_INVESTIGATION_TOOL_CALLS_TOTAL,
    AI_MODEL_ESTIMATED_COST_USD_TOTAL,
    AI_MODEL_TOKENS_TOTAL,
    LocalAITraceRecord,
    get_current_trace_ids,
    get_tracer,
    record_ai_trace_metadata,
)
from app.models.incident import Incident
from app.models.investigation import (
    FeedbackRating,
    InvestigationRun,
    InvestigationStatus,
    InvestigationToolCall,
)
from app.repositories import audit_repo
from app.schemas.investigation import AIStatusResponse, InvestigationStartRequest


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _tenant_daily_usage(db: Session, organization_id: int) -> int:
    since = _utc_now() - timedelta(hours=24)
    count = db.scalar(
        select(func.count(InvestigationRun.id)).where(
            InvestigationRun.organization_id == organization_id,
            InvestigationRun.created_at >= since,
        )
    )
    return int(count or 0)


def get_ai_status(
    db: Session, *, organization_id: int, settings: Settings | None = None
) -> AIStatusResponse:
    cfg = settings or get_settings()
    used = _tenant_daily_usage(db, organization_id)
    if cfg.ai_provider_mode == "openai":
        configured = bool(cfg.openai_api_key and cfg.openai_model.strip())
        notice = (
            f"Live OpenAI Responses API configured (model={cfg.openai_model})."
            if configured
            else "AI_PROVIDER_MODE=openai but OPENAI_API_KEY is missing."
        )
        model_name = cfg.openai_model
    else:
        configured = True
        model_name = "mock-deterministic-v1"
        notice = "Running in deterministic MOCK mode (no external OpenAI API calls)."

    return AIStatusResponse(
        provider_mode=cfg.ai_provider_mode,
        model_name=model_name,
        configured=configured,
        prompt_version=cfg.ai_prompt_version,
        max_graph_steps=cfg.ai_max_graph_steps,
        max_tool_calls=cfg.ai_max_tool_calls,
        tenant_daily_used=used,
        tenant_daily_quota=cfg.ai_tenant_daily_quota,
        notice=notice,
    )


def start_investigation(
    db: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    incident_id: int,
    data: InvestigationStartRequest,
    settings: Settings | None = None,
    model_client: InvestigationModelClient | None = None,
    simulate_tool_timeout: bool = False,
) -> InvestigationRun:
    cfg = settings or get_settings()
    incident = db.scalar(
        select(Incident).where(
            Incident.id == incident_id,
            Incident.organization_id == organization_id,
            Incident.archived_at.is_(None),
        )
    )
    if incident is None:
        raise NotFoundError("Incident not found")

    if _tenant_daily_usage(db, organization_id) >= cfg.ai_tenant_daily_quota:
        raise RateLimitedError(
            f"Tenant daily AI investigation quota ({cfg.ai_tenant_daily_quota}) exceeded"
        )

    client = model_client or build_model_client(cfg)
    model_name = cfg.openai_model if cfg.ai_provider_mode == "openai" else "mock-deterministic-v1"

    started_dt = _utc_now()
    t0 = time.perf_counter()
    run = InvestigationRun(
        organization_id=organization_id,
        incident_id=incident.id,
        requested_by_user_id=actor_user_id,
        status=InvestigationStatus.RUNNING.value,
        provider_mode=cfg.ai_provider_mode,
        model_name=model_name,
        prompt_version=cfg.ai_prompt_version,
        window_hours=data.window_hours,
        started_at=started_dt,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    tracer = get_tracer("opspilot.ai")
    with tracer.start_as_current_span("ai.investigation.run"):
        state = run_investigation_graph(
            db=db,
            organization_id=organization_id,
            incident=incident,
            run=run,
            settings=cfg,
            model_client=client,
            mock_scenario=data.mock_scenario,
            simulate_tool_timeout=simulate_tool_timeout,
        )
        trace_id, _ = get_current_trace_ids()

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    tool_records = state.get("tool_records", [])
    for rec in tool_records:
        AI_INVESTIGATION_TOOL_CALLS_TOTAL.labels(
            tool_name=rec.tool_name, status=rec.status.value
        ).inc()
        db.add(
            InvestigationToolCall(
                organization_id=organization_id,
                investigation_id=run.id,
                step_number=rec.step_number,
                tool_name=rec.tool_name,
                status=rec.status.value,
                input_summary_json=rec.input_summary,
                output_count=len(rec.items),
                latency_ms=rec.latency_ms,
                error_message=rec.error_message,
            )
        )

    run.graph_steps = int(state.get("graph_steps", 0))
    run.tool_calls_count = len(tool_records)
    run.latency_ms = elapsed_ms
    run.evidence_bundle_json = [item.model_dump() for item in state.get("evidence_bundle", [])]
    run.completed_at = _utc_now()

    synthesis = state.get("synthesis")
    if synthesis is not None:
        run.input_tokens = synthesis.input_tokens
        run.output_tokens = synthesis.output_tokens
        run.estimated_cost_usd = synthesis.estimated_cost_usd

    if state.get("cancelled"):
        run.status = InvestigationStatus.CANCELLED.value
        run.error_message = state.get("error_message")
    elif state.get("error_message") or state.get("validated_report") is None:
        run.status = InvestigationStatus.FAILED.value
        run.error_message = state.get("error_message") or "Investigation failed validation"
    else:
        run.status = InvestigationStatus.COMPLETED.value
        report = state["validated_report"]
        run.report_json = report.model_dump()

    AI_INVESTIGATION_DURATION_SECONDS.labels(
        provider_mode=run.provider_mode, status=run.status
    ).observe(elapsed_ms / 1000.0)
    AI_MODEL_TOKENS_TOTAL.labels(provider_mode=run.provider_mode, direction="input").inc(
        run.input_tokens
    )
    AI_MODEL_TOKENS_TOTAL.labels(provider_mode=run.provider_mode, direction="output").inc(
        run.output_tokens
    )
    if run.estimated_cost_usd:
        AI_MODEL_ESTIMATED_COST_USD_TOTAL.labels(provider_mode=run.provider_mode).inc(
            run.estimated_cost_usd
        )
    record_ai_trace_metadata(
        LocalAITraceRecord(
            trace_id=trace_id,
            provider_mode=run.provider_mode,
            model_name=run.model_name,
            prompt_version=run.prompt_version,
            status=run.status,
            tool_calls_count=run.tool_calls_count,
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
            latency_ms=run.latency_ms,
        ),
        langfuse_enabled=cfg.langfuse_enabled,
    )

    audit_repo.append_event(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=f"ai.investigation.{run.status}",
        target_type="investigation_run",
        target_id=str(run.id),
        metadata={
            "incident_id": incident.id,
            "provider_mode": run.provider_mode,
            "model_name": run.model_name,
            "tool_calls_count": run.tool_calls_count,
            "latency_ms": run.latency_ms,
        },
    )
    db.commit()
    return get_investigation(db, organization_id=organization_id, investigation_id=run.id)


def list_incident_investigations(
    db: Session, *, organization_id: int, incident_id: int
) -> list[InvestigationRun]:
    incident = db.scalar(
        select(Incident.id).where(
            Incident.id == incident_id,
            Incident.organization_id == organization_id,
            Incident.archived_at.is_(None),
        )
    )
    if incident is None:
        raise NotFoundError("Incident not found")
    return list(
        db.scalars(
            select(InvestigationRun)
            .options(joinedload(InvestigationRun.tool_calls))
            .where(
                InvestigationRun.organization_id == organization_id,
                InvestigationRun.incident_id == incident_id,
            )
            .order_by(InvestigationRun.created_at.desc(), InvestigationRun.id.desc())
        )
        .unique()
        .all()
    )


def get_investigation(
    db: Session, *, organization_id: int, investigation_id: int
) -> InvestigationRun:
    run = (
        db.scalars(
            select(InvestigationRun)
            .options(joinedload(InvestigationRun.tool_calls))
            .where(
                InvestigationRun.id == investigation_id,
                InvestigationRun.organization_id == organization_id,
            )
        )
        .unique()
        .first()
    )
    if run is None:
        raise NotFoundError("Investigation run not found")
    return run


def cancel_investigation(
    db: Session, *, organization_id: int, actor_user_id: int, investigation_id: int
) -> InvestigationRun:
    run = get_investigation(db, organization_id=organization_id, investigation_id=investigation_id)
    if run.status not in {InvestigationStatus.PENDING.value, InvestigationStatus.RUNNING.value}:
        raise ConflictError(f"Cannot cancel investigation in '{run.status}' state")
    run.status = InvestigationStatus.CANCELLED.value
    run.completed_at = _utc_now()
    run.error_message = "Cancelled by user"
    audit_repo.append_event(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="ai.investigation.cancelled",
        target_type="investigation_run",
        target_id=str(run.id),
        metadata={"incident_id": run.incident_id},
    )
    db.commit()
    return get_investigation(db, organization_id=organization_id, investigation_id=run.id)


def submit_feedback(
    db: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    investigation_id: int,
    rating: FeedbackRating,
    note: str | None,
) -> InvestigationRun:
    run = get_investigation(db, organization_id=organization_id, investigation_id=investigation_id)
    run.human_feedback_rating = rating.value
    run.human_feedback_note = note.strip() if note else None
    run.feedback_by_user_id = actor_user_id
    run.feedback_at = _utc_now()
    audit_repo.append_event(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="ai.investigation.feedback",
        target_type="investigation_run",
        target_id=str(run.id),
        metadata={"rating": rating.value},
    )
    db.commit()
    return get_investigation(db, organization_id=organization_id, investigation_id=run.id)
