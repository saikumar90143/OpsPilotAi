# ADR-0005 — Observability Baseline: Request IDs, Structured Logs, Health Probes

**Status:** Accepted  
**Date:** 2026-11-21  
**Phase:** Phase 1 — Foundation Hardening

---

## Context

Operators need to correlate a failing request with its log lines, and orchestrators (Docker,
Kubernetes, load balancers) need distinct signals for "process alive" vs "able to serve".
Secrets (database passwords) must never appear in logs or responses (AGENTS.md §3, §9).

## Decision

- **Correlation ID:** every HTTP request gets an ID — the inbound `X-Request-ID` if it is
  1–128 chars of `[A-Za-z0-9._-]`, otherwise a new UUID4 (hex). Stored in a `ContextVar`,
  added to every log record, echoed in the `X-Request-ID` response header and in error bodies.
- **Logging:** stdlib `logging` only (no structlog/loguru). JSON lines when
  `APP_ENV=production` (or `LOG_FORMAT=json`, which Compose sets), readable console otherwise.
  One access-log line per request from the middleware (uvicorn access log disabled).
- **Redaction at format time:** formatters pass every output string through `redact()`, which
  masks URL passwords and `password=/secret=/token=/api_key=` values — covering messages,
  arguments, and tracebacks. Settings hide `database_url` from `repr` and from validation
  errors; startup logs use the redacted URL.
- **Probes:** `GET /health/live` (no I/O, always 200 while the process serves HTTP) and
  `GET /health/ready` (`SELECT 1`; 200 `ready` or 503 `not_ready` with
  `checks.database = ok | unavailable`, never connection details). PostgreSQL connections use
  a bounded `connect_timeout` so readiness fails fast. Legacy `GET /health` is kept, marked
  deprecated.
- **CLI check:** `python -m app.db_check` reports redacted URL, server version and Alembic
  revision (exit 1 if unreachable).

## Consequences

- Log lines are machine-parseable in containers; request IDs can be propagated by a future
  frontend or gateway.
- Regex redaction is best-effort; code must still avoid logging secrets deliberately.
- OpenTelemetry/metrics remain Phase 8 work.
