# OpsPilot AI — Build Tracker

**Last updated:** Phase 12 — Release Readiness & Recruiter Demonstration (2026-11-21)

---

## Phase Status

| Phase | Name | Status | Owner | Started | Completed |
|-------|------|--------|-------|---------|-----------|
| 0 | Audit & Governance Documentation | ✅ DONE (folded into Phase 1) | Agent | 2026-11-20 | 2026-11-20 |
| 1 | Foundation Hardening | ✅ DONE | Agent | 2026-11-20 | 2026-11-21 |
| 2 | Organizations, Auth & Tenant Isolation | ✅ DONE | Agent | 2026-11-21 | 2026-11-21 |
| 3 | Core Incident-Management Domain (Backend) | ✅ DONE | Agent | 2026-11-21 | 2026-11-21 |
| 4 | Webhook Ingestion & Background Queue | ✅ DONE | Agent | 2026-11-21 | 2026-11-21 |
| 5 | Next.js Operations Dashboard | ✅ DONE | Agent | 2026-11-21 | 2026-11-21 |
| 6 | GitHub Read-Only Connector | ✅ DONE | Agent | 2026-11-21 | 2026-11-21 |
| 7 | Evidence Layer (Logs & Engineering KB) | ✅ DONE | Agent | 2026-11-21 | 2026-11-21 |
| 8 | Read-Only AI Investigation Copilot | ✅ DONE | Agent | 2026-11-21 | 2026-11-21 |
| 9 | Controlled External Write Actions | ✅ DONE | Agent | 2026-11-21 | 2026-11-21 |
| 10 | Observability & AI Evaluation | ✅ DONE | Agent | 2026-11-21 | 2026-11-21 |
| 11 | Security & Reliability Hardening | ✅ DONE | Agent | 2026-11-21 | 2026-11-21 |
| 12 | Release Readiness & Recruiter Demo | ✅ DONE (awaiting user review) | Agent | 2026-11-21 | 2026-11-21 |

---

## Phase 1 Checkpoint Gates

| Gate | Criterion | Status |
|------|-----------|--------|
| P1-01 | Existing API behavior functional (4 existing tests + 9 compatibility tests pass) | ✅ PASS |
| P1-02 | Alembic upgrade/downgrade/drift check on SQLite | ✅ PASS (`test_migrations.py`) |
| P1-03 | Alembic upgrade head creates clean schema on PostgreSQL 16.14 | ✅ PASS (`test_postgres.py` + `migrate` service) |
| P1-04 | App starts locally (uvicorn) | ✅ PASS (`/health/live` 200, `/health/ready` 200) |
| P1-05 | App starts via Docker Compose (`db` → `migrate` → `api`) | ✅ PASS (`api` & `db` healthy, `migrate` exited 0) |
| P1-06 | `/health/live` → 200 OK | ✅ PASS (200 even when DB stopped) |
| P1-07 | `/health/ready` → 200 when DB available | ✅ PASS (SQLite & PostgreSQL) |
| P1-08 | `/health/ready` → 503 when DB unreachable | ✅ PASS (tested in `test_health.py` & `docker compose stop db`) |
| P1-09 | `ruff check .` exits 0 | ✅ PASS |
| P1-10 | `ruff format --check .` exits 0 | ✅ PASS (33 files) |
| P1-11 | `mypy app` exits 0 | ✅ PASS (21 source files) |
| P1-12 | All pytest tests pass (SQLite + PostgreSQL) | ✅ PASS (55 passed, 0 failed, 0 skipped) |
| P1-13 | PostgreSQL persistence across container restarts | ✅ PASS (`docker compose restart db api`, incident ID 1 persisted) |
| P1-14 | `.env.example` contains no real credentials; `.env` git-ignored | ✅ PASS |
| P1-15 | `opspilot.db` preserved untouched and not committed | ✅ PASS (SHA256 verified identical) |
| P1-16 | README documents venv setup, migrations, tests, troubleshooting | ✅ PASS |

---

## Requirement Traceability Matrix

### OPS-CORE — Core Incident Management

| ID | Requirement | Phase | Implementation File(s) | Test File(s) | Status |
|----|-------------|-------|----------------------|-------------|--------|
| OPS-CORE-001 | Create incident | 1 | `app/api/v1/incidents.py`, `app/services/incidents.py` | `tests/test_incidents.py` | ✅ |
| OPS-CORE-002 | List incidents with pagination | 1 | `app/api/v1/incidents.py`, `app/services/incidents.py` | `tests/test_incidents.py` | ✅ |
| OPS-CORE-003 | Retrieve incident by ID | 1 | `app/api/v1/incidents.py`, `app/services/incidents.py` | `tests/test_incidents.py` | ✅ |
| OPS-CORE-004 | Update incident status (enforced state machine) | 1 / 3 | `app/api/v1/incidents.py`, `app/services/incidents.py` | `tests/test_incidents.py`, `tests/test_incident_domain.py` | ✅ |
| OPS-CORE-005 | Soft-delete / archive | 2 | `app/api/v1/incidents.py`, `app/repositories/incident_repo.py` | `tests/test_incidents.py` | ✅ |
| OPS-CORE-006 | Org-scoped incidents | 2 | `app/repositories/incident_repo.py`, `app/services/incidents.py` | `tests/test_tenant_isolation.py`, `tests/test_postgres.py` | ✅ |
| OPS-CORE-007 | Incident timeline, comments, evidence, concurrency | 3 | `app/models/incident_details.py`, `app/services/incidents.py` | `tests/test_incident_domain.py`, `tests/test_postgres.py` | ✅ |

### OPS-SEC — Security and Access Control

| ID | Requirement | Phase | Implementation File(s) | Test File(s) | Status |
|----|-------------|-------|----------------------|-------------|--------|
| OPS-SEC-001 | Endpoints require auth | 2 | `app/api/deps.py` | `tests/test_auth.py`, `tests/test_errors.py` | ✅ |
| OPS-SEC-002 | JWT + rotating refresh cookies + CSRF | 2 | `app/core/security.py`, `app/api/v1/auth.py` | `tests/test_auth.py` | ✅ |
| OPS-SEC-003 | Argon2id password hashing | 2 | `app/core/security.py` | `tests/test_auth.py` | ✅ |
| OPS-SEC-004 | RBAC (`OWNER`/`ADMIN`/`ENGINEER`/`VIEWER`) | 2 | `app/core/permissions.py`, `app/api/deps.py` | `tests/test_rbac.py` | ✅ |
| OPS-SEC-005 | Tenant-scoped queries | 2 | `app/repositories/` | `tests/test_tenant_isolation.py`, `tests/test_postgres.py` | ✅ |
| OPS-SEC-006 | IDOR prevention | 2 | `app/repositories/`, `app/services/` | `tests/test_tenant_isolation.py`, `tests/test_postgres.py` | ✅ |
| OPS-SEC-007 | Human approval gate | 6 | — | — | ⬜ |
| OPS-SEC-008 | Immutable audit log | 2 / 6 | `app/models/audit_log.py`, `app/repositories/audit_repo.py` | `tests/test_audit.py` | ✅ (Phase 2 scope) |
| OPS-SEC-009 | Secrets never logged | 1 | `app/core/config.py`, `app/core/logging.py` | `tests/test_settings.py` | ✅ |
| OPS-SEC-010 | Rate limiting on auth | 2 | `app/core/rate_limit.py`, `app/api/deps.py` | `tests/test_auth.py` | ✅ |

### OPS-INGEST — Webhook Ingestion

| ID | Requirement | Phase | Implementation File(s) | Test File(s) | Status |
|----|-------------|-------|----------------------|-------------|--------|
| OPS-INGEST-001 | Alertmanager webhook | 4 | `app/integrations/alertmanager.py`, `app/api/v1/webhooks.py` | `tests/test_webhooks.py`, `tests/test_postgres.py` | ✅ |
| OPS-INGEST-002 | Reject malformed payloads | 4 | `app/integrations/alertmanager.py`, `app/api/v1/webhooks.py` | `tests/test_webhooks.py` | ✅ |
| OPS-INGEST-003 | Idempotent ingestion | 4 | `app/models/inbound_event.py`, `app/services/ingestion_service.py` | `tests/test_webhooks.py`, `tests/test_postgres.py` | ✅ |
| OPS-INGEST-004 | Redis/Celery queue | 4 | `app/worker.py`, `docker-compose.yml` | `tests/test_webhooks.py` + Compose `worker` | ✅ |
| OPS-INGEST-005 | Retry with backoff | 4 | `app/services/ingestion_service.py`, `app/worker.py` | `tests/test_webhooks.py` | ✅ |
| OPS-INGEST-006 | Dead-letter handling | 4 | `app/services/ingestion_service.py`, `app/api/v1/integrations.py` | `tests/test_webhooks.py` | ✅ |
| OPS-INGEST-007 | Raw inbound event log | 4 | `app/models/inbound_event.py`, `app/api/v1/integrations.py` | `tests/test_webhooks.py` | ✅ |

### OPS-UI — Frontend Dashboard

| ID | Requirement | Phase | Implementation File(s) | Test File(s) | Status |
|----|-------------|-------|----------------------|-------------|--------|
| OPS-UI-001 | Incident list page | 5 | `frontend/src/app/incidents/page.tsx` | `frontend/e2e/smoke.spec.ts` | ✅ |
| OPS-UI-002 | Incident detail page | 5 | `frontend/src/app/incidents/[id]/page.tsx` | `frontend/e2e/smoke.spec.ts` | ✅ |
| OPS-UI-003 | Responsive / accessible layout | 5 | `frontend/src/components/AppShell.tsx` | `frontend/e2e/smoke.spec.ts` (desktop + mobile) | ✅ |
| OPS-UI-004 | Loading states / empty states | 5 | `frontend/src/components/Feedback.tsx` | `frontend/src/components/Badges.test.tsx` | ✅ |
| OPS-UI-005 | Auth login/logout | 5 | `frontend/src/app/login/page.tsx`, `frontend/src/lib/auth.tsx` | `frontend/src/lib/api.test.ts`, `frontend/e2e/smoke.spec.ts` | ✅ |
| OPS-UI-006 | Action approval queue | 6 | — | — | ⬜ |
| OPS-UI-007 | Admin integration settings | 6 | `frontend/src/app/settings/page.tsx`, `app/api/v1/github.py` | `backend/tests/test_github.py` | ✅ |

### OPS-AI — AI Investigation

| ID | Requirement | Phase | Implementation File(s) | Test File(s) | Status |
|----|-------------|-------|----------------------|-------------|--------|
| OPS-AI-001 | Trigger AI investigation | 5 | — | — | ⬜ |
| OPS-AI-002 | OpenAI Responses API | 5 | — | — | ⬜ |
| OPS-AI-003 | LangGraph workflow | 5 | — | — | ⬜ |
| OPS-AI-004 | Confidence labeling | 5 | — | — | ⬜ |
| OPS-AI-005 | Evidence citations | 5 | — | — | ⬜ |
| OPS-AI-006 | Structured InvestigationReport | 5 | — | — | ⬜ |
| OPS-AI-007 | Mock adapter | 5 | — | — | ⬜ |
| OPS-AI-008 | Langfuse tracing | 8 | — | — | ⬜ |
| OPS-AI-009 | Tenant-scoped AI tools | 5 | — | — | ⬜ |

### OPS-ACT — Action Approval

| ID | Requirement | Phase | Implementation File(s) | Test File(s) | Status |
|----|-------------|-------|----------------------|-------------|--------|
| OPS-ACT-001 | ProposedAction model | 6 | — | — | ⬜ |
| OPS-ACT-002 | Approve/reject via API + UI | 6 | — | — | ⬜ |
| OPS-ACT-003 | Re-verify auth at execution | 6 | — | — | ⬜ |
| OPS-ACT-004 | Idempotent execution | 6 | — | — | ⬜ |
| OPS-ACT-005 | Jira adapter (mock) | 6 | — | — | ⬜ |
| OPS-ACT-006 | Slack adapter (mock) | 6 | — | — | ⬜ |
| OPS-ACT-007 | Audit record per action | 6 | — | — | ⬜ |

### OPS-OBS — Observability

| ID | Requirement | Phase | Implementation File(s) | Test File(s) | Status |
|----|-------------|-------|----------------------|-------------|--------|
| OPS-OBS-001 | Structured logs + correlation ID | 1 | `app/core/logging.py`, `app/api/middleware.py` | `tests/test_logging.py`, `tests/test_health.py` | ✅ |
| OPS-OBS-002 | `/health/live` | 1 | `app/api/health.py` | `tests/test_health.py` | ✅ |
| OPS-OBS-003 | `/health/ready` | 1 | `app/api/health.py` | `tests/test_health.py` | ✅ |
| OPS-OBS-004 | OpenTelemetry | 8 | — | — | ⬜ |
| OPS-OBS-005 | Prometheus metrics | 8 | — | — | ⬜ |
| OPS-OBS-006 | Grafana dashboard | 8 | — | — | ⬜ |
| OPS-OBS-007 | Langfuse AI tracing | 8 | — | — | ⬜ |

### OPS-DEPLOY — Infrastructure & DX

| ID | Requirement | Phase | Implementation File(s) | Test File(s) | Status |
|----|-------------|-------|----------------------|-------------|--------|
| OPS-DEPLOY-001 | Docker Compose | 1 | `docker-compose.yml` | Manual | ✅ |
| OPS-DEPLOY-002 | Alembic migrations | 1 | `alembic/`, `alembic.ini` | `tests/test_postgres.py` | ✅ |
| OPS-DEPLOY-003 | `.env.example` with placeholders | 1 | `.env.example` | Manual | ✅ |
| OPS-DEPLOY-004 | Ruff + mypy pass | 1 | `pyproject.toml` | CI step | ✅ |
| OPS-DEPLOY-005 | Reproducible local setup (Windows) | 1 | `README.md` | Manual | ✅ |
| OPS-DEPLOY-006 | Redis + Celery in Docker Compose | 4 | `docker-compose.yml`, `app/worker.py` | Compose `redis` + `worker` | ✅ |
| OPS-DEPLOY-007 | GitHub Actions CI | 9 | `.github/workflows/ci.yml` | CI | ✅ |
| OPS-DEPLOY-008 | Playwright E2E tests | 9 / 12 | `frontend/playwright.config.ts`, `frontend/e2e/auth.setup.ts`, `frontend/e2e/smoke.spec.ts` | `npx playwright test --reporter=list` | ✅ |

---

## Phase 1 Test Results

Recorded 2026-11-21 after final edits (`.\scripts\check.ps1` + `pytest -v --cov=app --cov-report=term-missing`):

| Suite | Tests | Passed | Failed | Skipped | Notes |
|---|---|---|---|---|---|
| Unit & SQLite API / Migrations | 49 | 49 | 0 | 0 | `test_incidents`, `test_settings`, `test_database`, `test_health`, `test_errors`, `test_logging`, `test_migrations` |
| PostgreSQL (`@pytest.mark.postgres`) | 6 | 6 | 0 | 0 | Executed against `db-test` (PostgreSQL 16) via `TEST_POSTGRES_URL` |
| **Total** | **55** | **55** | **0** | **0** | **97% statement coverage** (`469` stmts, `16` missed) |
| Ruff (`ruff check .`, `ruff format --check .`) | — | Pass | — | — | 33 files checked |
| mypy (`mypy app`) | — | Pass | — | — | 21 source files checked |

---

## Known Technical Debt

| ID | Description | Phase Introduced | Target Phase |
|----|-------------|-----------------|-------------|
| TD-001 | No git repository — no version history | Phase 0 | Phase 1 (resolved) |
| TD-002 | No virtual environment — global Python installs | Phase 0 | Phase 1 (resolved) |
| TD-003 | `httpx` → `httpx2` deprecation warning | Phase 0 | Phase 1 (resolved by switching to httpx2) |
| TD-004 | CPython 3.13 bytecode residue in `__pycache__` | Phase 0 | Phase 1 (gitignored) |
| TD-005 | No authentication on any endpoint | Phase 0 | Phase 2 (resolved) |
| TD-006 | No tenant isolation | Phase 0 | Phase 2 (resolved) |
| TD-007 | Coverage threshold not yet met for all modules | Phase 1 | Phase 2+ |

---

## Playwright E2E Verification (2026-11-22)

Verified against the live `docker compose --profile demo` stack (`postgres:16-alpine`, `redis:7-alpine`, `api`, `worker`, `frontend` at `http://localhost:3000`, zero mocked backend services):

- **Database & readiness checks**:
  - `docker compose exec -T api python -m app.db_check` → `Status: OK`, `Dialect: postgresql 16.14`, `Revision: 0008`
  - `curl.exe -s http://127.0.0.1:8000/health/ready` → `{"status":"ready","checks":{"database":"ok"}}`
- **Frontend static checks & unit tests**:
  - `npm run typecheck` (`tsc --noEmit`) → **PASS** (exit 0)
  - `npm run lint` (`eslint .`) → **PASS** (exit 0)
  - `npm run test` (`vitest run`) → **PASS** (2 test files, 4 tests passed)
- **Playwright E2E (`npx playwright test --reporter=list`)** with `E2E_DEMO_EMAIL`, `E2E_DEMO_PASSWORD`, and `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`:
  - `[setup] › e2e/auth.setup.ts` — `authenticate demo admin once` → **PASS** (`2.5s`, reusable `storageState`)
  - `[desktop] › e2e/smoke.spec.ts` (1280×800) — `overview, create deterministic incident, acknowledge, and run read-only AI investigation` → **PASS** (`6.8s`)
  - `[desktop] › e2e/smoke.spec.ts` (1280×800) — `navigate and verify live UI across events, evidence & KB, actions, and settings` → **PASS** (`4.2s`)
  - `[mobile] › e2e/smoke.spec.ts` (390×844) — `overview, create deterministic incident, acknowledge, and run read-only AI investigation` → **PASS** (`7.3s`)
  - `[mobile] › e2e/smoke.spec.ts` (390×844) — `navigate and verify live UI across events, evidence & KB, actions, and settings` → **PASS** (`4.6s`)
  - **Total:** **5 passed, 0 failed** (`19.6s`)
- **Backend PostgreSQL & Unit/API Verification (2026-11-22)**:
  - `pytest -m "not postgres" -q` → **108 passed, 9 deselected** (exit 0)
  - `pytest -m postgres -v` against `db-test` (`postgres:16-alpine` on `127.0.0.1:55432`) → **9 passed, 108 deselected** (exit 0)
  - `ruff check .`, `ruff format --check .` (`118` files), `mypy app --ignore-missing-imports` (`86` source files) → **PASS** (exit 0)
- **Known Notes**:
  - Each E2E run creates two deterministic `E2E Smoke <project> <timestamp>` incidents in the local demo DB so `Acknowledge` is always exercised on a fresh `open` incident without mutating seeded demo incidents.
  - On Windows where `%LOCALAPPDATA%\ms-playwright` is not installed, `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` can point to a local Chromium/Chrome binary; default Playwright browser resolution is preserved when unset.
