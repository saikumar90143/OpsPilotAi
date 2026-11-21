# ADR-0004 — Layering and the Error Response Contract

**Status:** Accepted  
**Date:** 2026-11-21  
**Phase:** Phase 1 — Foundation Hardening

---

## Context

The starter code kept HTTP handling, business rules, and persistence calls in one router
module, and errors used FastAPI's default `{"detail": ...}` body. AGENTS.md §9 requires a
consistent error shape `{error, message, request_id}`, and later phases (tenant isolation,
approval gates) need a place for business rules that is independent of HTTP.

## Decision

1. **Layers:** `api/` (routers, HTTP mapping) → `services/` (use cases, transactions) →
   SQLAlchemy `Session` + `models/`. `schemas/` hold Pydantic v2 I/O models; `core/` holds
   settings, database, logging, and transport-agnostic domain errors.
2. **No repository layer yet.** Four trivial queries do not justify an extra abstraction; the
   `Session` is the unit of work. Revisit in Phase 2 when tenant scoping adds mandatory query
   filters (a repository/query helper is the natural place to enforce `org_id`).
3. **Transactions:** `get_db()` yields one session per request and rolls back on any
   exception. Services commit explicitly at the end of each write use case.
4. **Error contract (intentional breaking change of error bodies only):** every non-2xx
   response is `{"error": <code>, "message": <text>, "request_id": <id>}`; validation errors
   add `details: [{loc, msg, type}]` (raw input is never echoed). Paths, methods, status codes,
   and success bodies are unchanged. No client consumed the old `detail` key.
5. **500 boundary:** a pure-ASGI middleware is the single place that catches unhandled
   exceptions, logs them with full context, and returns a generic `internal_error`.

## Consequences

- Routers are thin and testable; services can be reused by future workers/queues.
- Clients must read `message` instead of `detail` for error text.
- Adding a domain error = subclass `AppError` + map its code to a status in `api/errors.py`.

## Alternatives Considered

- **Keep `detail` alongside the new keys for one phase** — rejected: no consumers exist yet,
  and dual shapes invite clients to depend on the wrong one.
- **Generic repository classes** — rejected for now (speculative abstraction).
