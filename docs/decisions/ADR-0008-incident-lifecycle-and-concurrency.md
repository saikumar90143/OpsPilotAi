# ADR-0008 — Incident Lifecycle State Machine, Optimistic Concurrency, and Severity vs. Priority

**Status:** Accepted  
**Date:** 2026-11-21  
**Phase:** Phase 3 — Core Incident-Management Domain

---

## Context

Phase 1/2 allowed arbitrary `PATCH /api/v1/incidents/{id}/status` changes without enforcing
valid state transitions, lifecycle timestamps, concurrency checks, or incident timeline
history. Before adding webhook ingestion (Phase 4) and AI workflows (Phase 5), the core
incident domain must prevent invalid states and silent lost updates.

## Decisions

1. **Domain-enforced state machine:** `app/services/incidents.py` enforces `ALLOWED_TRANSITIONS`
   across `open`, `acknowledged`, `investigating`, `resolved`, and `closed`. Invalid
   transitions raise `ConflictError` (`409`). Lifecycle timestamps (`acknowledged_at`,
   `resolved_at`, `closed_at`) are managed exclusively by the service in UTC.
2. **Optimistic concurrency (`version`):** `incidents.version` starts at `1` and increments
   atomically via `UPDATE ... WHERE id = :id AND organization_id = :org_id AND version = :expected`.
   Clients may supply `version` in the JSON body or via `If-Match`; stale versions return `409`.
3. **Severity vs. Priority:** `severity` (`critical`, `high`, `medium`, `low`) measures
   **technical/business impact**. Priority (triage/SLA scheduling such as P1–P4) is distinct
   and intentionally deferred until SLA/routing rules exist.
4. **Related domain tables:** `incident_timeline_events`, `incident_comments`,
   `incident_evidence_refs`, `incident_affected_services`, and `incident_tags` are tenant-scoped
   relational tables managed by `incidents.py` without extra repository boilerplate.
5. **Pagination header:** `GET /api/v1/incidents` preserves `list[IncidentRead]` for backward
   compatibility and exposes total matching count via `X-Total-Count`.

## Consequences

- Concurrent updates never silently overwrite each other when callers pass `version` / `If-Match`.
- Every incident mutation records both an incident-scoped timeline event and an org-scoped
  security/domain audit record.
