# OpsPilot AI — Final Feature Traceability Matrix

| Area | Requirement | Implementation File(s) | Test File(s) | Demo Step |
|---|---|---|---|---|
| **Auth & Tenant Isolation** | Multi-tenant JWT/refresh cookies, CSRF, Argon2id, RBAC, IDOR prevention | `app/core/security.py`, `app/core/permissions.py`, `app/api/deps.py` | `test_auth.py`, `test_rbac.py`, `test_tenant_isolation.py`, `test_security_hardening.py` | Step 0 |
| **Incident Lifecycle** | Enforced state machine, optimistic concurrency, timeline, comments, evidence | `app/models/incident.py`, `app/services/incidents.py`, `app/api/v1/incidents.py` | `test_incident_domain.py`, `test_incidents.py`, `test_postgres.py` | Step 2 |
| **Event Ingestion** | Alertmanager v4 adapter, HMAC/Bearer auth, Redis/Celery queue, DLQ & simulator | `app/integrations/alertmanager.py`, `app/services/ingestion_service.py`, `app/worker.py` | `test_webhooks.py`, `test_postgres.py` | Step 1 |
| **GitHub Read-Only** | `SourceControlProvider`, `GitHubClient`, `MockGitHubAdapter`, webhook dedup | `app/integrations/scm/`, `app/services/github_service.py` | `test_github.py` | Step 2 |
| **Evidence & KB** | Redacted structured logs, `.md`/`.txt` KB upload, chunking, hybrid retrieval | `app/core/redaction.py`, `app/services/evidence_service.py`, `app/api/v1/evidence.py` | `test_evidence.py` | Step 2 |
| **AI Investigation** | OpenAI Responses API + Mock, bounded LangGraph, 4 read-only tools, citations | `app/ai/tools.py`, `app/ai/model_client.py`, `app/ai/graph.py`, `app/services/investigation_service.py` | `test_ai_investigation.py`, `test_evals.py` | Step 3 |
| **External Actions** | `ProposedAction` gate, Jira/Slack mock & live, allowlists, `payload_hash`, idempotency | `app/integrations/actions/`, `app/services/action_service.py`, `app/api/v1/actions.py` | `test_actions.py`, `test_security_hardening.py` | Step 4 |
| **Observability & Evals** | OTel traces, `/metrics`, Prometheus/Grafana, alerts, runbooks, `eval-dataset-v1.0` | `app/core/telemetry.py`, `app/evals/`, `observability/`, `docs/runbooks/` | `test_telemetry.py`, `test_evals.py` | Step 5 |
| **Frontend UI** | Next.js App Router dashboard, `/incidents`, `/evidence`, `/actions`, `/events`, `/settings` | `frontend/src/app/**`, `frontend/src/lib/api.ts` | `api.test.ts`, `Badges.test.tsx`, `e2e/smoke.spec.ts` | Steps 0–5 |
