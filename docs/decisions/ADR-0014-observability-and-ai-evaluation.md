# ADR-0014: Observability, Low-Cardinality Metrics & Offline AI Evaluation

- **Status:** Accepted (Phase 10)
- **Date:** 2026-11-21

## Context

Phase 10 makes OpsPilot AI measurable and diagnosable across HTTP requests, queue jobs, connectors, and AI investigations without leaking secrets or creating high-cardinality metric explosions.

## Decisions

1. **OpenTelemetry Tracing & Log Correlation (`app/core/telemetry.py`, `app/core/logging.py`)**
   - Instruments FastAPI HTTP requests, SQLAlchemy queries, Celery worker tasks, external connectors, and AI investigation spans using `opentelemetry-sdk`.
   - Injects active `trace_id` and `span_id` into structured JSON logs alongside `request_id` (`X-Request-ID`), with regex redaction applied to all string values.
   - AI trace metadata (`LocalAITraceRecord`) is recorded locally by default (`LANGFUSE_ENABLED=false`) so no external tracing service is required for local dev or CI.

2. **Prometheus Metrics & Cardinality Control (`GET /metrics`)**
   - Exposes `opspilot_http_*`, `opspilot_webhook_*`, `opspilot_queue_*`, `opspilot_connector_*`, `opspilot_incident_tta_seconds`/`ttr_seconds`, and `opspilot_ai_*` metrics.
   - Labels are restricted to bounded enums/templates (`method`, `route` template, `status_class`, `provider`, `mode`, `outcome`, `severity`, `tool_name`). Raw `user_id`, `incident_id`, `organization_id`, and exception strings are prohibited from metric labels.

3. **Opt-In Local Prometheus + Grafana Stack (`observability/` & `docker-compose.yml`)**
   - `docker compose --profile observability up -d` launches Prometheus (with `alerts.yml` for queue backlog, dead-letter growth, API 5xx rate, and AI failures) and Grafana (provisioned dashboard `opspilot-overview.json`).

4. **Deterministic Offline AI Evaluation (`backend/app/evals/`)**
   - `dataset_v1.json` (`eval-dataset-v1.0`) defines 5 synthetic cases covering corroborated failures, sparse/no-data uncertainty, conflicting evidence, and prompt injection.
   - `runner.py` runs deterministically in CI with `MockInvestigationModel` (and supports opt-in `--live` evaluation), outputting dated JSON reports with precision/recall/F1, citation validity, retrieval relevance, tool accuracy, unsupported-claim rate, latency, and token/cost totals.
