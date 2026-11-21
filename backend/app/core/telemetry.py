"""OpenTelemetry tracing, low-cardinality Prometheus metrics, and local AI trace metadata."""

from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from sqlalchemy import Engine

from app.core.config import Settings

# --- Low-cardinality Prometheus metrics (no user_id, incident_id, or raw exceptions) ---

HTTP_REQUESTS_TOTAL = Counter(
    "opspilot_http_requests_total",
    "Total HTTP requests by method, route template, and status class.",
    ["method", "route", "status_class"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "opspilot_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "route"],
)
HTTP_ERRORS_TOTAL = Counter(
    "opspilot_http_errors_total",
    "HTTP 4xx/5xx responses by method, route template, and status class.",
    ["method", "route", "status_class"],
)

WEBHOOK_EVENTS_TOTAL = Counter(
    "opspilot_webhook_events_total",
    "Inbound webhook receipts by provider and outcome.",
    ["provider", "outcome"],
)
QUEUE_DEPTH = Gauge(
    "opspilot_queue_depth",
    "Current inbound event queue depth by status.",
    ["status"],
)
QUEUE_JOB_AGE_SECONDS = Histogram(
    "opspilot_queue_job_age_seconds",
    "Age in seconds of queued jobs when processed.",
    ["status"],
)
QUEUE_RETRIES_TOTAL = Counter(
    "opspilot_queue_retries_total",
    "Total inbound event retries scheduled.",
    ["provider"],
)
QUEUE_DEAD_LETTERS_TOTAL = Counter(
    "opspilot_queue_dead_letters_total",
    "Total inbound events moved to dead-letter status.",
    ["provider"],
)

CONNECTOR_REQUESTS_TOTAL = Counter(
    "opspilot_connector_requests_total",
    "External connector calls by provider, mode, and outcome.",
    ["provider", "mode", "outcome"],
)
CONNECTOR_DURATION_SECONDS = Histogram(
    "opspilot_connector_duration_seconds",
    "External connector call latency in seconds.",
    ["provider", "mode"],
)

INCIDENT_TTA_SECONDS = Histogram(
    "opspilot_incident_tta_seconds",
    "Incident time-to-acknowledge in seconds.",
    ["severity"],
)
INCIDENT_TTR_SECONDS = Histogram(
    "opspilot_incident_ttr_seconds",
    "Incident time-to-resolve in seconds.",
    ["severity"],
)

AI_INVESTIGATION_DURATION_SECONDS = Histogram(
    "opspilot_ai_investigation_duration_seconds",
    "AI investigation execution duration in seconds.",
    ["provider_mode", "status"],
)
AI_INVESTIGATION_TOOL_CALLS_TOTAL = Counter(
    "opspilot_ai_investigation_tool_calls_total",
    "AI investigation tool calls by tool name and status.",
    ["tool_name", "status"],
)
AI_MODEL_TOKENS_TOTAL = Counter(
    "opspilot_ai_model_tokens_total",
    "AI model tokens consumed by provider mode and direction.",
    ["provider_mode", "direction"],
)
AI_MODEL_ESTIMATED_COST_USD_TOTAL = Counter(
    "opspilot_ai_model_estimated_cost_usd_total",
    "Estimated AI model cost in USD by provider mode.",
    ["provider_mode"],
)

_SPAN_EXPORTER: InMemorySpanExporter | None = None
_TRACING_CONFIGURED = False
_SQLALCHEMY_INSTRUMENTED = False


def configure_telemetry(settings: Settings) -> InMemorySpanExporter | None:
    """Initialize OpenTelemetry TracerProvider once for the process."""
    global _SPAN_EXPORTER, _TRACING_CONFIGURED
    if not settings.otel_enabled:
        return None
    if _TRACING_CONFIGURED:
        return _SPAN_EXPORTER

    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)
    _SPAN_EXPORTER = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(_SPAN_EXPORTER))
    trace.set_tracer_provider(provider)
    _TRACING_CONFIGURED = True
    return _SPAN_EXPORTER


def instrument_app(app: FastAPI, engine: Engine, settings: Settings) -> None:
    """Attach FastAPI and SQLAlchemy OpenTelemetry instrumentation safely."""
    global _SQLALCHEMY_INSTRUMENTED
    if not settings.otel_enabled:
        return
    configure_telemetry(settings)
    FastAPIInstrumentor.instrument_app(app, excluded_urls="/metrics,/health/live,/health/ready")
    if not _SQLALCHEMY_INSTRUMENTED:
        SQLAlchemyInstrumentor().instrument(engine=engine)
        _SQLALCHEMY_INSTRUMENTED = True


def get_tracer(name: str = "opspilot") -> trace.Tracer:
    return trace.get_tracer(name)


def get_current_trace_ids() -> tuple[str | None, str | None]:
    """Return hex (trace_id, span_id) if an active OTel span exists."""
    span = trace.get_current_span()
    ctx = span.get_span_context() if span is not None else None
    if ctx is None or not ctx.is_valid:
        return None, None
    return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")


def render_prometheus_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST


@dataclass(frozen=True)
class LocalAITraceRecord:
    trace_id: str | None
    provider_mode: str
    model_name: str
    prompt_version: str
    status: str
    tool_calls_count: int
    input_tokens: int
    output_tokens: int
    latency_ms: int


_LOCAL_AI_TRACES: list[LocalAITraceRecord] = []


def record_ai_trace_metadata(record: LocalAITraceRecord, *, langfuse_enabled: bool = False) -> None:
    """Record redacted AI trace metadata locally (no external Langfuse service required)."""
    del langfuse_enabled  # External Langfuse export is opt-in; local buffer always safe & offline.
    _LOCAL_AI_TRACES.append(record)
    if len(_LOCAL_AI_TRACES) > 200:
        del _LOCAL_AI_TRACES[:-200]


def get_recent_ai_traces() -> list[dict[str, Any]]:
    return [
        {
            "trace_id": r.trace_id,
            "provider_mode": r.provider_mode,
            "model_name": r.model_name,
            "prompt_version": r.prompt_version,
            "status": r.status,
            "tool_calls_count": r.tool_calls_count,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "latency_ms": r.latency_ms,
        }
        for r in _LOCAL_AI_TRACES
    ]
