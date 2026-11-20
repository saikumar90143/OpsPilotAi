# ADR-0001 — Begin with a Modular Monolith

**Status:** Accepted  
**Date:** 2026-11-20  
**Phase:** Phase 1 — Foundation Hardening

---

## Context

OpsPilot AI is in its early development phase with a single developer building toward a portfolio
demonstration. The eventual target architecture involves multiple concerns: incident management,
webhook ingestion, background task processing, AI workflow orchestration, and a web dashboard.

There is a decision to make about the initial system topology:
1. **Microservices** — each concern as a separately deployed service
2. **Modular monolith** — all concerns in one deployable unit with internal module boundaries
3. **Serverless** — functions-as-a-service (AWS Lambda, Cloud Run, etc.)

---

## Decision

We start with a **modular monolith** organized into clear domain modules within a single FastAPI
application (`backend/app/`):

```
backend/app/
├── api/          ← HTTP layer (routers, dependencies, error handlers)
├── core/         ← Cross-cutting concerns (config, database, logging)
├── models/       ← SQLAlchemy ORM models (persistence representation)
├── schemas/      ← Pydantic models (API wire format)
├── services/     ← Domain business logic (orchestrates models, enforces rules)
└── integrations/ ← External system connectors (Phase 4+)
```

Each module communicates through explicit Python interfaces (function calls, service classes), not
HTTP calls or message buses. The domain boundaries are enforced by code review and test coverage,
not network boundaries.

---

## Consequences

**Positive:**
- Fast to build and iterate — no inter-service latency or network serialization overhead.
- Easy to reason about — a single debugger session covers the entire call path.
- Straightforward local setup — one `uvicorn` process, one database, one Docker Compose file.
- Safe refactoring — IDE tooling (rename, find-references) works across the entire codebase.
- Clear upgrade path — when a module genuinely needs independent scaling, the internal boundary
  makes extraction tractable.

**Negative / Trade-offs:**
- A single process means a single failure domain. A bug that crashes the Python process
  takes down all features simultaneously. (Mitigation: health probes, container restart policies.)
- All modules share the same database. Schema changes affect the entire application.
  (Mitigation: Alembic migrations, careful review, tenant isolation at the query level.)
- Deployment scaling is coarse-grained (the whole app, not per-module). Acceptable for a
  single-node deployment; revisit if specific modules need independent scaling.

**Deferred decisions:**
- If the AI investigation workflow proves to have very high latency or resource usage, it can be
  extracted to a separate worker process (Celery already provides this boundary) without changing
  the monolith structure.
- If webhook ingestion volume becomes a bottleneck, the ingestion module can be extracted.
  The `integrations/` module boundary makes this safe.

---

## Alternatives Considered

### Microservices (Rejected)
Premature for this stage. Each service would require its own deployment, service discovery,
inter-service auth, distributed tracing, and network failure handling. This complexity cannot be
justified without a proven need driven by measured scale requirements.

### Serverless (Rejected)
Introduces vendor lock-in without proven need. Cold-start latency is incompatible with low-latency
incident investigation. Local development emulation is poor compared to running a real process.

---

## Review Trigger

Re-evaluate this decision if:
- Any single module consistently uses > 60% of available CPU or memory.
- Independent deployment cadences become necessary (different teams own different modules).
- A module's data model needs to diverge from the shared PostgreSQL schema.
