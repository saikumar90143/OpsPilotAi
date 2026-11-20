# ADR-0002 — Use Alembic for Schema Management

**Status:** Accepted  
**Date:** 2026-11-20  
**Phase:** Phase 1 — Foundation Hardening

---

## Context

The starter codebase used `Base.metadata.create_all(bind=engine)` in the FastAPI application
lifespan to create database tables on startup. This approach works for a first prototype but has
critical production limitations:

- It **cannot add or modify columns** to tables that already exist. Any schema change requires
  manual `ALTER TABLE` SQL or dropping and recreating the table (destroying data).
- It provides **no history** — there is no record of what the schema looked like at any prior
  point in time.
- It is **not reversible** — there is no mechanism to roll back a schema change.
- It **silently diverges** — if the Python model changes but the database is not reset, the app
  runs with a schema mismatch that may cause subtle data corruption.

---

## Decision

Use **Alembic** as the authoritative schema management mechanism. Specifically:

- `Base.metadata.create_all()` is removed from the production startup path.
- It is retained **only** in test fixtures (`conftest.py`) where in-memory SQLite databases
  are created fresh for each test run — no migration history is needed there.
- Every production schema change produces a versioned Alembic migration script in
  `backend/alembic/versions/`.
- Docker Compose runs `alembic upgrade head` before starting `uvicorn`.
- All migration scripts must include a working `downgrade()` function.
- Migrations are reviewed before being applied to production.

---

## Consequences

**Positive:**
- Schema changes are versioned, reviewable, and reversible.
- Multiple developers can work on schema changes without overwriting each other.
- The exact schema state at any point in time is recoverable from the migration history.
- CI can verify that migrations apply cleanly to a fresh PostgreSQL database.

**Negative / Trade-offs:**
- More initial setup (Alembic config, `env.py`, migration script template).
- Developers must remember to generate and commit migration scripts with model changes.
  Forgetting produces a schema drift that only manifests at deployment time.
  (Mitigation: CI check that runs `alembic check` to detect uncommitted model changes.)
- Alembic's autogenerate does not detect all types of schema changes (e.g., some PostgreSQL-specific
  column constraints). Migration scripts must be reviewed before application.

---

## Alternatives Considered

### Keep `create_all()` (Rejected)
Acceptable for a prototype; not acceptable once real data exists. The first schema change after
real users are onboarded would require a manual migration with no tooling support.

### Use a third-party migration tool (e.g., Flyway, Liquibase) (Rejected)
These tools are Java-based and would introduce a cross-language dependency into a Python project.
Alembic is the SQLAlchemy ecosystem standard; it integrates directly with our model metadata.

---

## Review Trigger

Re-evaluate if the SQLAlchemy/Alembic ecosystem is abandoned or if we move to a different ORM.
