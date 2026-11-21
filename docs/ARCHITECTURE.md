# OpsPilot AI — Architecture

## Current implemented state (Phase 5 — Next.js Operations Dashboard)

The platform consists of a Next.js App Router frontend (`frontend/`) and a modular FastAPI + Celery backend (`backend/`):

- **Frontend (`frontend/src/`):**
  - App Router with strict TypeScript, Tailwind CSS v4, and accessible responsive `AppShell` (desktop sidebar + mobile drawer).
  - Centralized `apiFetch` client using `HttpOnly` cookies (`credentials: "include"`) and double-submit `X-CSRF-Token` with automatic single-retry `401` refresh (never `localStorage`).
  - `incidents/[id]` (RBAC + state-machine lifecycle, `version` concurrency, assign, timeline, comments, evidence + read-only GitHub correlation, audit)
  - `settings` (org, members/roles, Alertmanager simulator, Read-Only GitHub Connector with `DEMO / MOCK` vs `LIVE` status, and clearly labelled Phase 7+ placeholders).
- **Source-control integration (`backend/app/integrations/scm/`):** `SourceControlProvider` protocol with read-only `GitHubClient` (GitHub App / PAT, ETags, `Link` pagination, rate limits, retries) and deterministic `MockGitHubAdapter`.

- **API layer (`backend/app/api/`):**
  - `health.py`: unversioned `/health/live` (process liveness, no I/O) and `/health/ready` (database `SELECT 1` check, returns `503` when unreachable without leaking connection strings). Legacy `/health` retained and marked deprecated.
  - `deps.py`: `get_auth_context()` (validates JWT access tokens from `HttpOnly` cookies or `Authorization: Bearer`, enforces double-submit `X-CSRF-Token` on cookie-authenticated mutations, and re-verifies active DB `Membership`), `require_permission()`, and `enforce_auth_rate_limit()`.
  - `v1/auth.py`: `/api/v1/auth/*` (`login`, `refresh` with rotation & reuse detection, `logout`, `accept-invite`, `me`).
  - `v1/organizations.py`: `/api/v1/organizations/current`, `/api/v1/memberships`, `/api/v1/invitations`, `/api/v1/audit-logs`.
  - `v1/incidents.py`: versioned, tenant-scoped `/api/v1/incidents` router (list, create, retrieve, status update, soft-delete/archive).
  - `middleware.py` & `errors.py`: `RequestContextMiddleware` (correlation `X-Request-ID`, structured access logging, single `500` boundary) and `{ "error", "message", "request_id" }` error envelope.
- **Service & Repository layers (`backend/app/services/`, `backend/app/repositories/`):**
  - `repositories/`: `incident_repo.py`, `auth_repo.py`, `audit_repo.py` — every tenant-owned query requires `organization_id: int` explicitly; cross-tenant lookups return `None` → `404`.
  - `services/`: `incidents.py`, `auth_service.py`, `org_service.py` — use cases own transactions and append sanitized `AuditLog` entries.
- **Core (`backend/app/core/`):** `config.py`, `database.py`, `logging.py`, `errors.py`, `security.py` (Argon2id + PyJWT), `permissions.py` (`OWNER`, `ADMIN`, `ENGINEER`, `VIEWER`), `rate_limit.py`.
- **Persistence (`backend/app/models/`, `backend/alembic/`):** PostgreSQL 16 is the primary supported database; SQLite is supported for local development and fast tests. Schema is managed exclusively by Alembic (`0001`, `0002`). See [docs/SECURITY.md](SECURITY.md) for the permission matrix and frontend auth contract.
- **Container topology (`docker-compose.yml`):** `db` (PostgreSQL 16, persistent named volume `opspilot_postgres_data`, no published host port) → `migrate` (one-shot `alembic upgrade head`) → `api` (bound to `127.0.0.1:8000`, `/health/ready` healthcheck), plus opt-in `db-test` (`--profile test`, ephemeral `tmpfs` on `127.0.0.1:55432`) for PostgreSQL integration tests.

## Planned architecture

```text
Monitoring / GitHub / Slack / Jira
              |
       Webhooks & Connectors
              |
       FastAPI Integration API
              |
      Validation / Idempotency
              |
       Event Queue (Redis)
              |
     Incident & Evidence Service
         /           \
  PostgreSQL       Log / Docs Index
      |                  |
      +---- AI Agent ----+
               |
       Evidence-backed plan
               |
        Human approval gate
               |
       Jira / Slack actions
```

## Technology choices

- **Next.js + React:** operations dashboard.
- **FastAPI + Pydantic:** typed Python API and validation.
- **PostgreSQL:** incidents, users, organizations, integrations, and audit events.
- **Redis:** asynchronous event processing when ingestion volume grows.
- **pgvector:** semantic retrieval over engineering runbooks and documentation.
- **LangGraph:** explicit, inspectable multi-step agent workflows after deterministic services exist.
- **OpenTelemetry + Langfuse:** application traces and AI-specific execution/evaluation data.
- **Docker:** reproducible local development and deployment packaging.

## Implemented Phase 2 API

| Method | Path | Auth / Role | Purpose |
|---|---|---|---|
| GET | `/health/live` | Public | Liveness probe (`200 {"status": "ok"}`) |
| GET | `/health/ready` | Public | Readiness probe (`200 ready` / `503 not_ready` via DB `SELECT 1`) |
| GET | `/health` | Public | Legacy health check (deprecated) |
| POST | `/api/v1/auth/login` | Public (rate-limited) | Issue `HttpOnly` access/refresh + CSRF cookies |
| POST | `/api/v1/auth/refresh` | Refresh cookie + CSRF | Rotate refresh token (with reuse detection) |
| POST | `/api/v1/auth/logout` | Session + CSRF | Revoke refresh family & clear cookies |
| POST | `/api/v1/auth/accept-invite` | Public (rate-limited) | Accept org invitation & start session |
| GET | `/api/v1/auth/me` | Authenticated | Current user, organization, and DB-verified role |
| GET / PATCH | `/api/v1/organizations/current` | `VIEWER`+ / `OWNER` | Read or rename active organization |
| GET / PATCH / DELETE | `/api/v1/memberships` | `VIEWER`+ / `ADMIN`+ | List or manage organization members |
| POST / GET / DELETE | `/api/v1/invitations` | `ADMIN`+ | Create, list, or revoke organization invitations |
| GET | `/api/v1/audit-logs` | `ADMIN`+ | Read append-only security/domain audit logs |
| GET / POST | `/api/v1/incidents` | `VIEWER`+ / `ENGINEER`+ | Filter/search/sort/paginate (`X-Total-Count`) or create incidents |
| GET / PATCH / DELETE | `/api/v1/incidents/{id}` | `VIEWER`+ / `ENGINEER`+ / `ADMIN`+ | Retrieve, update (with `version` concurrency), or archive incident |
| POST / PATCH | `/api/v1/incidents/{id}/acknowledge`, `resolve`, `reopen`, `assign`, `status` | `ENGINEER`+ | State-machine transitions & same-org assignment |
| GET / POST | `/api/v1/incidents/{id}/timeline`, `comments`, `evidence` | `VIEWER`+ / `ENGINEER`+ | Chronological timeline, notes, and evidence references |
| POST / GET / PATCH | `/api/v1/integrations` | `ADMIN`+ | Manage tenant Alertmanager configs (encrypted secrets) |
| POST | `/api/v1/integrations/{id}/rotate-secret`, `simulate` | `ADMIN`+ | Rotate signing secret (with grace) or run deterministic simulator |
| POST | `/api/v1/webhooks/alertmanager/{endpoint_token}` | HMAC / Bearer | Ingest Alertmanager v4 webhooks (persists receipt → Redis/Celery) |
| GET / POST | `/api/v1/events`, `/api/v1/events/{id}/replay` | `ADMIN`+ | Review inbound receipts/dead-letters and replay failed events |
| POST / GET | `/api/v1/evidence/logs`, `/logs/ingest`, `/logs/load-fixtures` | `VIEWER`+ / `ENGINEER`+ | Bounded UTC log search (secret/PII redacted) & synthetic log fixtures |
| POST / GET / DELETE | `/api/v1/evidence/kb/documents`, `/kb/search`, `/kb/load-fixtures` | `VIEWER`+ / `ADMIN`+ | Tenant KB upload (`.md`/`.txt`), versioning, re-index, hybrid retrieval |
| GET | `/api/v1/evidence/incidents/{id}/context` | `VIEWER`+ | Normalized incident context (bounded logs + KB citations) |
| GET | `/api/v1/ai/status` | `VIEWER`+ | Honest AI provider/model status, prompt version, and tenant daily quota |
| POST / GET | `/api/v1/incidents/{id}/investigations`, `/investigations/{id}`, `/cancel`, `/feedback` | `ENGINEER`+ / `VIEWER`+ | Bounded read-only LangGraph AI investigation, tool trace, citations, feedback |
| GET / POST | `/api/v1/action-connectors`, `/action-connectors/{id}/test` | `VIEWER`+ / `ADMIN`+ | Manage & test Jira/Slack action connectors (encrypted creds, allowlists) |
| POST / GET | `/api/v1/incidents/{id}/actions`, `/actions`, `/actions/{id}/approve`, `reject`, `execute` | `ENGINEER`+ / `VIEWER`+ | Human-gated external write proposals, separation of duties, idempotent execution |
| GET | `/metrics` | Unauthenticated (internal) | Prometheus text exposition of low-cardinality HTTP, queue, connector, TTA/TTR, and AI metrics |

## Next architecture increments

1. Add the read-only AI investigation workflow behind a mock/real adapter (Phase 6+).
3. Add idempotent webhook ingestion and an event queue with retry/dead-letter handling.
4. Add GitHub and monitoring connectors behind provider interfaces.
5. Build a dashboard that consumes the incident API.
6. Add a read-only investigation workflow and evaluation dataset.
7. Add explicit human approval and audit records for all write actions.
