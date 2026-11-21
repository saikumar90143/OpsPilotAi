# ADR-0006 — Docker Compose Topology and Credential Handling

**Status:** Accepted  
**Date:** 2026-11-21  
**Phase:** Phase 1 — Foundation Hardening

---

## Context

The starter `docker-compose.yml` hard-coded the PostgreSQL password, published PostgreSQL on
`0.0.0.0:5432`, published the API on all interfaces, and relied on `create_all` at API startup.

## Decision

- **Credentials from the root `.env` only** (git-ignored). Compose uses `${VAR:?message}` so a
  missing value fails fast with a clear error. `.env.example` holds placeholders only.
- **Services:**
  - `db` — `postgres:16-alpine`, named volume `opspilot_postgres_data`, `pg_isready`
    healthcheck, **no published port**.
  - `migrate` — one-shot `alembic upgrade head` after `db` is healthy.
  - `api` — starts after `migrate` completes successfully; published on `127.0.0.1:8000` only;
    healthcheck calls `/health/ready`; runs as a non-root user.
  - `db-test` (profile `test`, opt-in) — ephemeral PostgreSQL in `tmpfs` on
    `127.0.0.1:55432` for integration tests; never touches the persistent volume.
- **Project name pinned** (`name: opspilot-ai`) so the volume name is stable regardless of the
  checkout directory name.
- Runtime image installs `requirements.txt` only; dev tools live in `requirements-dev.txt`.

## Consequences

- Host tools cannot reach the dev database directly; use
  `docker compose exec db psql -U <user> <db>` or `docker compose exec api python -m app.db_check`.
- PostgreSQL only reads `POSTGRES_*` when initialising an empty volume. Changing the password
  in `.env` later requires `ALTER USER` inside the database (documented in README); volumes are
  never deleted by tooling.
- Passwords must be URL-safe because they are interpolated into `DATABASE_URL`.
