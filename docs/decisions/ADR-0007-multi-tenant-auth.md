# ADR-0007 — Multi-Tenant Identity, Argon2id, Cookie/CSRF Auth, and Tenant Repositories

**Status:** Accepted  
**Date:** 2026-11-21  
**Phase:** Phase 2 — Organizations, Auth & Tenant Isolation

---

## Context

Phase 1 left all incident endpoints unauthenticated and single-tenant. Before adding frontend
dashboards (Phase 3) or external integrations (Phase 4+), the platform requires strict
multi-tenant isolation, RBAC (`OWNER`, `ADMIN`, `ENGINEER`, `VIEWER`), secure browser session
handling, and an append-only security audit trail.

## Decisions

1. **Password hashing:** Use **Argon2id** (`argon2-cffi`) instead of `bcrypt` (superseding the
   initial Phase 0 note in `SYSTEM_SPEC.md`). Argon2id is memory-hard, has no 72-byte password
   truncation limit, and avoids `passlib` maintenance issues on Python 3.12+.
2. **Tokens & browser storage:** Short-lived JWT access tokens (`pyjwt`, HS256, 15 min) +
   opaque SHA-256-hashed rotating refresh tokens with `family_id` reuse detection. Delivered
   exclusively via `HttpOnly` `SameSite=Lax` cookies (`opspilot_access` on `/`,
   `opspilot_refresh` scoped to `/api/v1/auth`) + double-submit `opspilot_csrf` / `X-CSRF-Token`.
   Tokens are never stored in `localStorage`.
3. **Server-side membership re-verification:** Every authenticated request re-queries the
   active `memberships` row in PostgreSQL/SQLite so role demotions or removals take effect
   immediately rather than waiting for JWT expiry.
4. **Repository layer for tenant isolation:** Per ADR-0004's review trigger, introduce
   `app/repositories/` where every tenant-owned query requires `organization_id: int` derived
   exclusively from `AuthContext`. Cross-tenant lookups return `404` to prevent IDOR inference.
5. **No public self-registration:** Users join organizations via admin/owner invitations
   (`accept-invite`) or the CLI-only `python -m app.bootstrap` tool (blocked in production).

## Consequences

- Frontend (Phase 3) must use `credentials: "include"` and echo `X-CSRF-Token` on mutations.
- Single-worker in-memory rate limiting is sufficient for Phase 2 and will move to Redis in
  Phase 4 when horizontal workers are introduced.
