# OpsPilot AI — Build Tracker

**Last updated:** Phase 1 — Foundation Hardening (2026-11-20)

---

## Phase Status

| Phase | Name | Status | Owner | Started | Completed |
|-------|------|--------|-------|---------|-----------|
| 0 | Audit & Governance Documentation | ✅ DONE (folded into Phase 1) | Agent | 2026-11-20 | 2026-11-20 |
| 1 | Foundation Hardening | 🔄 IN PROGRESS | Agent | 2026-11-20 | — |
| 2 | Organizations, Auth & Tenant Isolation | ⬜ NOT STARTED | — | — | — |
| 3 | Next.js Dashboard (Read-Only) | ⬜ NOT STARTED | — | — | — |
| 4 | Webhook Ingestion & Background Queue | ⬜ NOT STARTED | — | — | — |
| 5 | AI Investigation Workflow | ⬜ NOT STARTED | — | — | — |
| 6 | Action Approval Gate & Audit Trail | ⬜ NOT STARTED | — | — | — |
| 7 | GitHub Read-Only Connector | ⬜ NOT STARTED | — | — | — |
| 8 | Observability (OTel + Langfuse) | ⬜ NOT STARTED | — | — | — |
| 9 | CI/CD & Quality Gates | ⬜ NOT STARTED | — | — | — |

---

## Phase 1 Checkpoint Gates

| Gate | Criterion | Status |
|------|-----------|--------|
| P1-01 | Existing API behavior functional (4 existing tests pass) | ✅ PASS |
| P1-02 | Alembic upgrade head creates clean schema on SQLite | ⬜ Pending |
| P1-03 | Alembic upgrade head creates clean schema on PostgreSQL | ⬜ Pending (Docker required) |
| P1-04 | App starts locally (uvicorn) | ⬜ Pending |
| P1-05 | App starts via Docker Compose | ⬜ Pending (Docker required) |
| P1-06 | `/health/live` → 200 OK | ⬜ Pending |
| P1-07 | `/health/ready` → 200 when DB available | ⬜ Pending |
| P1-08 | `/health/ready` → 503 when DB unreachable | ⬜ Pending |
| P1-09 | `ruff check .` exits 0 | ⬜ Pending |
| P1-10 | `ruff format --check .` exits 0 | ⬜ Pending |
| P1-11 | `mypy app --ignore-missing-imports` exits 0 | ⬜ Pending |
| P1-12 | All pytest tests pass (SQLite) | ⬜ Pending |
| P1-13 | PostgreSQL tests auto-skipped (not marked PASSED) when Docker down | ⬜ Pending |
| P1-14 | `.env.example` contains no real credentials | ✅ PASS (reviewed) |
| P1-15 | `opspilot.db` preserved and not committed | ⬜ Pending |
| P1-16 | README documents venv setup, migrations, tests, troubleshooting | ⬜ Pending |

---

## Requirement Traceability Matrix

### OPS-CORE — Core Incident Management

| ID | Requirement | Phase | Implementation File(s) | Test File(s) | Status |
|----|-------------|-------|----------------------|-------------|--------|
| OPS-CORE-001 | Create incident | 1 | `app/api/v1/incidents.py`, `app/services/incident_service.py` | `tests/test_incidents.py` | ✅ |
| OPS-CORE-002 | List incidents with pagination | 1 | `app/api/v1/incidents.py`, `app/services/incident_service.py` | `tests/test_incidents.py` | ✅ |
| OPS-CORE-003 | Retrieve incident by ID | 1 | `app/api/v1/incidents.py`, `app/services/incident_service.py` | `tests/test_incidents.py` | ✅ |
| OPS-CORE-004 | Update incident status | 1 | `app/api/v1/incidents.py`, `app/services/incident_service.py` | `tests/test_incidents.py` | ✅ |
| OPS-CORE-005 | Soft-delete / archive | 2 | — | — | ⬜ |
| OPS-CORE-006 | Org-scoped incidents | 2 | — | — | ⬜ |
| OPS-CORE-007 | Incident timeline | 6 | — | — | ⬜ |

### OPS-SEC — Security and Access Control

| ID | Requirement | Phase | Implementation File(s) | Test File(s) | Status |
|----|-------------|-------|----------------------|-------------|--------|
| OPS-SEC-001 | Endpoints require auth | 2 | — | — | ⬜ |
| OPS-SEC-002 | JWT auth | 2 | — | — | ⬜ |
| OPS-SEC-003 | Bcrypt passwords | 2 | — | — | ⬜ |
| OPS-SEC-004 | RBAC | 2 | — | — | ⬜ |
| OPS-SEC-005 | Tenant-scoped queries | 2 | — | — | ⬜ |
| OPS-SEC-006 | IDOR prevention | 2 | — | — | ⬜ |
| OPS-SEC-007 | Human approval gate | 6 | — | — | ⬜ |
| OPS-SEC-008 | Immutable audit log | 6 | — | — | ⬜ |
| OPS-SEC-009 | Secrets never logged | 1 | `app/core/config.py`, `app/core/logging.py` | `tests/test_settings.py` | ✅ |
| OPS-SEC-010 | Rate limiting on auth | 2 | — | — | ⬜ |

### OPS-INGEST — Webhook Ingestion

| ID | Requirement | Phase | Implementation File(s) | Test File(s) | Status |
|----|-------------|-------|----------------------|-------------|--------|
| OPS-INGEST-001 | Alertmanager webhook | 4 | — | — | ⬜ |
| OPS-INGEST-002 | Reject malformed payloads | 4 | — | — | ⬜ |
| OPS-INGEST-003 | Idempotent ingestion | 4 | — | — | ⬜ |
| OPS-INGEST-004 | Redis/Celery queue | 4 | — | — | ⬜ |
| OPS-INGEST-005 | Retry with backoff | 4 | — | — | ⬜ |
| OPS-INGEST-006 | Dead-letter handling | 4 | — | — | ⬜ |
| OPS-INGEST-007 | Raw inbound event log | 4 | — | — | ⬜ |

### OPS-UI — Frontend Dashboard

| ID | Requirement | Phase | Implementation File(s) | Test File(s) | Status |
|----|-------------|-------|----------------------|-------------|--------|
| OPS-UI-001 | Incident list page | 3 | — | — | ⬜ |
| OPS-UI-002 | Incident detail page | 3 | — | — | ⬜ |
| OPS-UI-003 | Responsive / accessible layout | 3 | — | — | ⬜ |
| OPS-UI-004 | Loading states / empty states | 3 | — | — | ⬜ |
| OPS-UI-005 | Auth login/logout | 3 | — | — | ⬜ |
| OPS-UI-006 | Action approval queue | 6 | — | — | ⬜ |
| OPS-UI-007 | Admin integration settings | 7 | — | — | ⬜ |

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
| OPS-OBS-001 | Structured logs + correlation ID | 1 | `app/core/logging.py` | `tests/test_health.py` | ✅ |
| OPS-OBS-002 | `/health/live` | 1 | `app/api/v1/health.py` | `tests/test_health.py` | ✅ |
| OPS-OBS-003 | `/health/ready` | 1 | `app/api/v1/health.py` | `tests/test_health.py` | ✅ |
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
| OPS-DEPLOY-006 | Redis + Celery in Docker Compose | 4 | — | — | ⬜ |
| OPS-DEPLOY-007 | GitHub Actions CI | 9 | — | — | ⬜ |
| OPS-DEPLOY-008 | Playwright E2E tests | 9 | — | — | ⬜ |

---

## Phase 1 Test Results

> Updated at phase completion.

| Suite | Tests | Passed | Failed | Skipped | Notes |
|-------|-------|--------|--------|---------|-------|
| SQLite (all) | — | — | — | — | Pending |
| PostgreSQL (`@pytest.mark.postgres`) | — | — | — | — | Pending (Docker not running) |

---

## Known Technical Debt

| ID | Description | Phase Introduced | Target Phase |
|----|-------------|-----------------|-------------|
| TD-001 | No git repository — no version history | Phase 0 | Phase 1 (resolved) |
| TD-002 | No virtual environment — global Python installs | Phase 0 | Phase 1 (resolved) |
| TD-003 | `httpx` → `httpx2` deprecation warning | Phase 0 | Phase 1 (resolved by switching to httpx2) |
| TD-004 | CPython 3.13 bytecode residue in `__pycache__` | Phase 0 | Phase 1 (gitignored) |
| TD-005 | No authentication on any endpoint | Phase 0 | Phase 2 |
| TD-006 | No tenant isolation | Phase 0 | Phase 2 |
| TD-007 | Coverage threshold not yet met for all modules | Phase 1 | Phase 2+ |
