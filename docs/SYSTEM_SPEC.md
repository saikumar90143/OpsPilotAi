# OpsPilot AI — System Specification

**Version:** 0.1 (Phase 1 baseline)  
**Status:** Living document — updated each phase.

---

## 1. Product Vision

OpsPilot AI is an enterprise incident investigation and workflow automation platform for software
engineering and IT operations teams. It correlates monitoring alerts, application logs, source-control
activity, engineering runbooks, and incident history, then uses an evidence-backed AI workflow to help
on-call engineers understand what went wrong and prepare a coordinated response — faster and with more
context than manually querying each system.

**What it is not:** an autonomous remediation system. All external write actions require a human to
review and explicitly approve a proposed action before it executes.

---

## 2. Primary Personas

### 2.1 On-Call Software Engineer
- **Goal:** Understand and resolve a production incident as quickly as possible.
- **Pain:** Evidence is scattered across five or more tools; correlation takes 15–40 minutes manually.
- **Needs:** Prioritized incident list, correlated evidence, AI-generated investigation summary.

### 2.2 Site Reliability Engineer (SRE)
- **Goal:** Reduce mean time to resolution and improve post-incident learning.
- **Pain:** Runbooks are outdated; alert fatigue leads to missed signals.
- **Needs:** Alert ingestion with deduplication, runbook indexing, historical pattern matching.

### 2.3 Platform Engineering Lead
- **Goal:** Understand systemic reliability trends across services.
- **Pain:** No single view across incidents, deployments, and monitoring changes.
- **Needs:** Service-level incident history, deployment-change correlation, integration health.

### 2.4 IT Operations Lead
- **Goal:** Coordinate cross-team incident response and stakeholder communication.
- **Pain:** Unclear ownership, delayed communications, manual status updates.
- **Needs:** Incident status view, action approval gate, audit trail of decisions.

### 2.5 Organization Administrator
- **Goal:** Configure integrations, manage user access, and audit platform activity.
- **Pain:** No visibility into what the AI system does or what actions were taken automatically.
- **Needs:** Integration settings, user management, immutable audit log, role configuration.

---

## 3. Problem Statement

During a production incident, evidence is spread across monitoring dashboards, log aggregators, GitHub
commit history, Slack conversations, Jira tickets, and internal runbooks. Engineers must context-switch
between all of them while also troubleshooting the problem. This information-gathering phase regularly
accounts for more than half of total incident duration.

No existing tool automatically correlates these signals, attributes evidence to a specific incident,
and presents it with explicit confidence labeling. OpsPilot AI fills this gap.

---

## 4. Core Workflows

### WF-01: Alert Ingestion
1. Alertmanager (or another monitoring tool) sends a webhook POST to OpsPilot.
2. The platform validates the payload schema and generates an idempotency key.
3. If the alert has already been received (duplicate), the event is logged and discarded.
4. A new `Incident` is created (or an existing one is updated) with the alert as evidence.
5. The engineer sees the incident in the dashboard immediately.

### WF-02: Manual Incident Creation
1. An engineer creates an incident via the dashboard or API.
2. The incident is validated and persisted with an `open` status.
3. The engineer can add description, severity, affected service, and initial notes.

### WF-03: AI Investigation
1. An engineer requests an investigation on an open incident.
2. The AI workflow collects evidence from configured read-only sources (logs, metrics, GitHub).
3. Each finding is tagged with a confidence level: `confirmed`, `likely`, `possible`, or `unknown`.
4. Every claim cites the specific evidence item that supports it.
5. A structured investigation report is returned. No root cause is stated without supporting evidence.

### WF-04: Action Approval
1. The AI workflow proposes a remediation action (e.g., create Jira ticket, post Slack message).
2. The action is stored as `ProposedAction` with `status=pending`.
3. An authorized engineer reviews the action details in the dashboard.
4. The engineer explicitly approves or rejects it.
5. On approval, the platform executes the action exactly once (idempotent) and creates an audit record.
6. On rejection, the action is marked rejected with the reviewer's notes.

### WF-05: Organization Administration
1. An admin configures integration credentials (GitHub token, Slack bot, Jira project).
2. The admin manages user accounts and role assignments.
3. All platform actions (approvals, rejections, config changes) are appended to an immutable audit log.
4. The admin can export or view the audit log at any time.

---

## 5. Functional Requirements

### OPS-CORE — Core Incident Management

| ID | Requirement | Phase |
|----|-------------|-------|
| OPS-CORE-001 | Create an incident with title, description, service, severity, and source | Phase 1 |
| OPS-CORE-002 | List incidents, newest first, with pagination (limit/offset) | Phase 1 |
| OPS-CORE-003 | Retrieve a single incident by ID | Phase 1 |
| OPS-CORE-004 | Update incident status through the lifecycle: open → investigating → resolved → closed | Phase 1 |
| OPS-CORE-005 | Soft-delete / archive incidents (no hard deletes of incident records) | Phase 2 |
| OPS-CORE-006 | Incidents are scoped to an organization (tenant isolation) | Phase 2 |
| OPS-CORE-007 | Incident history/timeline of status changes and actions | Phase 6 |

### OPS-SEC — Security and Access Control

| ID | Requirement | Phase |
|----|-------------|-------|
| OPS-SEC-001 | All endpoints except `/health/*` require authentication | Phase 2 |
| OPS-SEC-002 | JWT-based authentication (access + refresh tokens) | Phase 2 |
| OPS-SEC-003 | Passwords hashed with bcrypt; never stored in plaintext | Phase 2 |
| OPS-SEC-004 | Role-based access control: `admin`, `responder`, `viewer` | Phase 2 |
| OPS-SEC-005 | Every DB query on tenant-owned data filtered by `org_id` | Phase 2 |
| OPS-SEC-006 | IDOR prevention: user cannot access another org's incidents | Phase 2 |
| OPS-SEC-007 | All external write actions require a human approval gate | Phase 6 |
| OPS-SEC-008 | Immutable append-only audit log for all significant actions | Phase 6 |
| OPS-SEC-009 | Secrets never logged or returned in API responses | Phase 1 |
| OPS-SEC-010 | Rate limiting on auth endpoints | Phase 2 |

### OPS-INGEST — Webhook Ingestion and Event Queue

| ID | Requirement | Phase |
|----|-------------|-------|
| OPS-INGEST-001 | Accept Alertmanager webhook payloads at `POST /api/v1/ingest/alertmanager` | Phase 4 |
| OPS-INGEST-002 | Validate and reject malformed payloads with 400 (not 500) | Phase 4 |
| OPS-INGEST-003 | Idempotent ingestion: duplicate alerts create one incident only | Phase 4 |
| OPS-INGEST-004 | Enqueue events to Redis for async processing via Celery | Phase 4 |
| OPS-INGEST-005 | Retry failed tasks with exponential backoff and jitter | Phase 4 |
| OPS-INGEST-006 | Dead-letter handling: failed tasks stored with reason | Phase 4 |
| OPS-INGEST-007 | Raw inbound event log for debugging and re-processing | Phase 4 |

### OPS-UI — Frontend Dashboard

| ID | Requirement | Phase |
|----|-------------|-------|
| OPS-UI-001 | Incident list page with severity badges and status chips | Phase 3 |
| OPS-UI-002 | Incident detail page with timeline | Phase 3 |
| OPS-UI-003 | Responsive layout; accessible (WCAG 2.1 AA target) | Phase 3 |
| OPS-UI-004 | Loading skeletons and honest empty states (no fake data) | Phase 3 |
| OPS-UI-005 | Authentication login/logout flows | Phase 3 |
| OPS-UI-006 | Action approval queue page | Phase 6 |
| OPS-UI-007 | Admin integration settings page | Phase 7 |

### OPS-AI — AI Investigation Workflow

| ID | Requirement | Phase |
|----|-------------|-------|
| OPS-AI-001 | Trigger an AI investigation on a specific incident | Phase 5 |
| OPS-AI-002 | Use OpenAI Responses API (not Assistants) with explicit tool/function calling | Phase 5 |
| OPS-AI-003 | LangGraph workflow for inspectable, bounded investigation steps | Phase 5 |
| OPS-AI-004 | Each finding labeled: confirmed / likely / possible / unknown | Phase 5 |
| OPS-AI-005 | Every claim cites its evidence source (file, metric, commit, log line) | Phase 5 |
| OPS-AI-006 | Structured `InvestigationReport` output (Pydantic model) | Phase 5 |
| OPS-AI-007 | Deterministic mock adapter when no OpenAI key is configured | Phase 5 |
| OPS-AI-008 | AI trace logging via Langfuse (or compatible local equivalent) | Phase 8 |
| OPS-AI-009 | Evidence must be tenant-scoped; no cross-org data leakage to AI tools | Phase 5 |

### OPS-ACT — Action Proposals and Approval

| ID | Requirement | Phase |
|----|-------------|-------|
| OPS-ACT-001 | AI workflow produces `ProposedAction` records, not direct writes | Phase 6 |
| OPS-ACT-002 | Approve or reject a proposed action via API and UI | Phase 6 |
| OPS-ACT-003 | Authorization re-verified at execution time, not just approval time | Phase 6 |
| OPS-ACT-004 | Approved action executed exactly once (idempotent) | Phase 6 |
| OPS-ACT-005 | Jira ticket creation adapter (mock by default; real via config) | Phase 6 |
| OPS-ACT-006 | Slack message adapter (mock by default; real via config) | Phase 6 |
| OPS-ACT-007 | Audit record created on every approve, reject, or execution event | Phase 6 |

### OPS-OBS — Observability

| ID | Requirement | Phase |
|----|-------------|-------|
| OPS-OBS-001 | Structured JSON logs with correlation ID on every request | Phase 1 |
| OPS-OBS-002 | `/health/live` — process liveness probe | Phase 1 |
| OPS-OBS-003 | `/health/ready` — readiness probe checking database connectivity | Phase 1 |
| OPS-OBS-004 | OpenTelemetry traces and metrics | Phase 8 |
| OPS-OBS-005 | Prometheus `/metrics` endpoint | Phase 8 |
| OPS-OBS-006 | Grafana dashboard for application metrics | Phase 8 |
| OPS-OBS-007 | Langfuse or equivalent for AI trace evaluation | Phase 8 |

### OPS-DEPLOY — Infrastructure and Developer Experience

| ID | Requirement | Phase |
|----|-------------|-------|
| OPS-DEPLOY-001 | Docker Compose for local PostgreSQL + API + supporting services | Phase 1 |
| OPS-DEPLOY-002 | Alembic migrations as authoritative schema management | Phase 1 |
| OPS-DEPLOY-003 | `.env.example` with dummy placeholders; real `.env` never committed | Phase 1 |
| OPS-DEPLOY-004 | Ruff lint/format and mypy type checks pass on CI | Phase 1 |
| OPS-DEPLOY-005 | Reproducible local setup documented for Windows PowerShell | Phase 1 |
| OPS-DEPLOY-006 | Redis + Celery worker in Docker Compose | Phase 4 |
| OPS-DEPLOY-007 | GitHub Actions CI pipeline | Phase 9 |
| OPS-DEPLOY-008 | Playwright E2E tests for high-value journeys | Phase 9 |

---

## 6. Non-Functional Requirements

| Attribute | Target | Measurement |
|-----------|--------|-------------|
| API p95 latency | < 200 ms for incident CRUD | Measured via OpenTelemetry in Phase 8 |
| Investigation latency | < 30 s for a mock investigation; < 120 s with real AI | Measured in Phase 5 |
| Availability | 99.5% in a single-node local deployment | Uptime monitoring in Phase 8 |
| Test coverage | ≥ 60% line coverage (backend); increasing each phase | `pytest-cov` report |
| Secret exposure | Zero credentials in source control or logs | Manual + automated checks each phase |
| Auth bypass | Zero IDOR or privilege escalation in test suite | Tenant isolation tests in Phase 2 |

---

## 7. Explicit Non-Goals for MVP

- Autonomous remediation without human approval.
- Replacing existing monitoring, ticketing, or source-control systems.
- Claiming a definitive root cause when evidence only supports a hypothesis.
- Automatically deploying code or modifying production infrastructure.
- Multi-region or high-availability clustering (this is a single-node application).
- Kubernetes orchestration (Docker Compose only for now).
- Claiming performance or cost benchmarks without measured evidence.

---

## 8. Success Metrics

These are targets for a pilot; baseline must be measured before reporting results.

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Alert-to-summary time | Reduce by ≥ 30% vs. manual baseline | Timed trials with synthetic incidents |
| AI evidence citation rate | ≥ 95% of findings have a cited source | Automated evaluation in Phase 5 |
| Proposed action approval rate | Measure and report (no fabricated target) | Audit log counts |
| Integration event success rate | ≥ 99% of valid webhooks create an incident | Integration tests in Phase 4 |
| Cost per investigation | Measure and report (no fabricated target) | OpenAI usage API in Phase 5 |

> **Important:** Do not publish benchmark numbers until they have been measured with a repeatable
> evaluation dataset on this specific deployment. Fabricated numbers undermine trust.

---

*Document created: Phase 1 — Foundation Hardening*
