# OpsPilot AI — Test Strategy

**Version:** 0.1 (Phase 1 baseline)  
**Last updated:** 2026-11-20

---

## 1. Test Pyramid

```
            ┌─────────────────┐
            │  E2E / Playwright │   ← Phase 9 (high-value journeys only)
            └────────┬────────┘
            ┌────────┴────────┐
            │  Frontend (Vitest) │   ← Phase 3 (components, hooks)
            └────────┬────────┘
            ┌────────┴────────────────────┐
            │  Security / IDOR Tests        │  ← Phase 2 (tenant isolation, auth bypass)
            └────────┬────────────────────┘
            ┌────────┴───────────────────────────┐
            │  PostgreSQL Integration Tests        │  ← Phase 1+ (real DB, @pytest.mark.postgres)
            └────────┬───────────────────────────┘
            ┌────────┴─────────────────────────────────┐
            │  API / Integration Tests (FastAPI + SQLite) │  ← Phase 1+ (all phases)
            └────────┬─────────────────────────────────┘
            ┌────────┴───────────────────────────────────────┐
            │  Unit Tests (pure functions, no I/O)              │  ← Phase 1+ (widest base)
            └───────────────────────────────────────────────┘
```

**Principle:** Tests in lower layers run everywhere (no dependencies). Tests in higher layers run
only when their dependencies are available (Docker, real API key, browser).

---

## 2. Test Layers

### 2.1 Unit Tests
**What:** Pure Python functions with no database, network, or file I/O.  
**Examples:** Schema validation, settings validation, URL sanitization helpers, service logic with mocked dependencies.  
**Location:** `backend/tests/test_settings.py`, `backend/tests/test_*.py` (functions that don't use `client` fixture)  
**Runs:** Everywhere, always. No prerequisites.  
**Tool:** `pytest`

### 2.2 API / Integration Tests (SQLite)
**What:** FastAPI endpoints tested end-to-end using `TestClient` with an in-memory SQLite database.  
**Examples:** CRUD endpoints, error shapes, status code validation, pagination boundaries.  
**Location:** `backend/tests/test_incidents.py`, `backend/tests/test_health.py`, `backend/tests/test_error_shape.py`  
**Runs:** Everywhere (in-memory SQLite, no Docker).  
**Tool:** `pytest` + `fastapi.testclient.TestClient`  
**Fixture:** `conftest.py::test_client` — creates schema via `Base.metadata.create_all()` on in-memory SQLite, tears down after each test module.

### 2.3 PostgreSQL Integration Tests
**What:** Tests that require a real PostgreSQL database, including Alembic migration round-trips and driver-specific behavior.  
**Examples:** `alembic upgrade head` / `downgrade -1` on a real DB; Postgres-specific constraint behavior.  
**Location:** `backend/tests/test_postgres.py`  
**Marker:** `@pytest.mark.postgres`  
**Auto-skip:** If `TEST_POSTGRES_URL` environment variable is unset, the test is **SKIPPED** (not PASSED).  
**Tool:** `pytest`

**To run PostgreSQL tests:**
```powershell
# 1. Start Docker Desktop
# 2. Start PostgreSQL container:
docker compose up db -d

# 3. Wait for healthy:
docker compose ps

# 4. Set the test URL and run only postgres-marked tests:
$env:TEST_POSTGRES_URL = "postgresql+psycopg://opspilot:local_dev_password@localhost:5432/opspilot"
pytest -v -m postgres
```

### 2.4 Tenant Isolation Tests (Phase 2+)
**What:** Verify that a user in organization A cannot access data belonging to organization B.  
**Examples:** `GET /api/v1/incidents/{id}` where the incident belongs to a different org → 404 (not 403, to avoid leaking existence).  
**Location:** `backend/tests/test_tenant_isolation.py` (Phase 2)  
**Marker:** `@pytest.mark.tenant`  
**Tool:** `pytest`

### 2.5 Contract Tests (Phase 4+)
**What:** Verify that inbound webhook payloads conform to expected schemas; verify that outbound API responses match documented schemas.  
**Examples:** Alertmanager webhook with missing `alerts` field → 400. Response body matches `IncidentRead` schema.  
**Location:** `backend/tests/test_contracts.py` (Phase 4)  
**Tool:** `pytest` + Pydantic schema validation

### 2.6 Frontend Unit Tests (Phase 3+)
**What:** React component rendering, hook behavior, API client response handling.  
**Location:** `frontend/src/**/*.test.tsx`  
**Tool:** Vitest + React Testing Library  
**Runs:** `npm test -- --run` (single pass) or `npm test` (watch mode)

### 2.7 Security Tests (Phase 2+)
**What:** Authentication bypass attempts, IDOR checks, privilege escalation, rate limiting.  
**Examples:** Accessing any incident endpoint without a JWT → 401. Accessing another org's incident → 404. Accessing a restricted role action as a viewer → 403.  
**Location:** `backend/tests/test_security.py` (Phase 2)  
**Tool:** `pytest`

### 2.8 AI Evaluation Tests (Phase 5+)
**What:** Verify that every AI finding cites a source, that confidence labels are always one of the allowed values, and that no root cause is stated without supporting evidence.  
**Location:** `backend/tests/test_ai_evaluation.py` (Phase 5)  
**Tool:** `pytest` + mock AI adapter

### 2.9 Performance Baselines (Phase 8+)
**What:** Measure p50/p95 latency for key endpoints under realistic load; compare against targets in SYSTEM_SPEC.md.  
**Tool:** `locust` or `k6` (decision in Phase 8)  
**Important:** Results are measured and reported. Fabricated benchmark numbers are not acceptable.

### 2.10 End-to-End Tests (Phase 9+)
**What:** Browser-based tests for high-value user journeys.  
**Examples:** Incident list loads; incident detail navigates from list; approval gate approve flow.  
**Location:** `frontend/e2e/`  
**Tool:** Playwright

---

## 3. Tools & Configuration

| Tool | Purpose | Config location |
|------|---------|----------------|
| `pytest` | Test runner (backend) | `backend/pyproject.toml [tool.pytest.ini_options]` |
| `pytest-cov` | Coverage reporting | `backend/pyproject.toml [tool.coverage.*]` |
| `Vitest` | Test runner (frontend) | `frontend/vitest.config.ts` (Phase 3) |
| `Playwright` | E2E browser tests | `frontend/playwright.config.ts` (Phase 9) |
| `Ruff` | Lint + format | `backend/pyproject.toml [tool.ruff]` |
| `mypy` | Static type checking | `backend/pyproject.toml [tool.mypy]` |

---

## 4. Coverage Targets

| Phase | Line Coverage Target | Rationale |
|-------|---------------------|-----------|
| Phase 1 | ≥ 60% | Foundation; config and health endpoints fully tested |
| Phase 2 | ≥ 65% | Auth and isolation code well-tested |
| Phase 3 | ≥ 65% | Frontend adds Vitest coverage |
| Phase 5+ | ≥ 70% | AI workflow paths tested with mock adapter |

Coverage is a minimum floor, not a goal. 100% coverage does not guarantee correctness.

---

## 5. What Is NOT Tested

| Scenario | Reason | Mitigation |
|----------|--------|-----------|
| Real OpenAI API responses | Cost and non-determinism | Mock adapter in Phase 5 |
| Real GitHub API rate limits | External dependency | Mock adapter in Phase 7 |
| Real Slack/Jira delivery | Side effects; requires credentials | Mock adapter in Phase 6 |
| Performance under sustained load | Out of scope until Phase 8 | Noted as gap |
| Browser compatibility beyond Chromium | Out of scope for portfolio demo | Playwright uses Chromium |

---

## 6. Test Failure Policy

1. **Never** skip or weaken a failing test to make CI green.
2. If a test reveals a real bug, the bug is fixed in the same phase.
3. If a test cannot run due to an environmental dependency (e.g., Docker not running), it is
   marked `SKIPPED` with a human-readable reason — never `PASSED`.
4. If a new test is added that tests not-yet-implemented behavior, mark it
   `@pytest.mark.xfail(reason="Phase N — not implemented yet", strict=True)` and implement
   the behavior in that phase.

---

## 7. Running the Full Test Suite

```powershell
# From backend/
cd backend

# Fast path (SQLite only, no Docker)
pytest -v --tb=short

# With coverage
pytest --cov=app --cov-report=term-missing

# PostgreSQL tests only (requires Docker + running DB)
$env:TEST_POSTGRES_URL = "postgresql+psycopg://opspilot:local_dev_password@localhost:5432/opspilot"
pytest -v -m postgres

# Lint and type checks
ruff check .
ruff format --check .
mypy app --ignore-missing-imports
```
