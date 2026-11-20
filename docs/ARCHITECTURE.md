# OpsPilot AI — Initial Architecture

## Current milestone

The starter backend provides a FastAPI service and a relational incident model. It supports local SQLite development and PostgreSQL through Docker Compose. The initial API is intentionally small so the developer can understand each layer before adding integrations and AI orchestration.

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

## Initial API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Process health check |
| GET | `/api/v1/incidents` | List recent incidents (`limit` 1–100) |
| POST | `/api/v1/incidents` | Create an incident |
| GET | `/api/v1/incidents/{id}` | Retrieve an incident |
| PATCH | `/api/v1/incidents/{id}/status` | Update workflow status |

## Next architecture increments

1. Add Alembic migrations and database health checks.
2. Add organizations, users, authentication, RBAC, and tenant-scoped queries before exposing the service to external users.
3. Add idempotent webhook ingestion and an event queue with retry/dead-letter handling.
4. Add GitHub and monitoring connectors behind provider interfaces.
5. Build a dashboard that consumes the incident API.
6. Add a read-only investigation workflow and evaluation dataset.
7. Add explicit human approval and audit records for all write actions.
