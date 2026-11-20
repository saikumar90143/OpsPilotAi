# OpsPilot AI — Agent Engineering Contract

This file is the authoritative set of rules for any AI agent (or human contributor) working in this
repository. It is loaded as persistent workspace context. Follow every rule unconditionally.

---

## 1. Phase Gate Protocol

- Work on **one phase only** when explicitly prompted. Never begin later phases unprompted.
- **Plan first, then wait for approval** before writing any application code or modifying files.
- At every phase end: run tests, capture results, write a checkpoint report, then **stop**.
- If a checkpoint criterion fails, fix that phase before moving on. Do not skip forward.

## 2. Change Control

- **Never** commit, push, publish, or deploy without an explicit user request.
- **Never** overwrite `.env`, local databases (`*.db`), or uncommitted user changes.
- Inspect the working tree before making changes; preserve unrelated work.
- Document every file created, modified, or deleted and explain why.

## 3. Security Non-Negotiables

- **No secrets in source.** `.env.example` contains dummy placeholders only.
- **No real credentials** in any file, log line, error response, or test fixture.
- Redact `DATABASE_URL` passwords and all secret fields before logging.
- Enforce tenant/org isolation on every database query that touches tenant-owned data.
- Verify permissions server-side on every request. Never trust frontend-only checks.

## 4. Test Mandate

- Every phase adds tests appropriate to its scope.
- **Never** delete, skip (`xfail`/`skip`), or weaken a failing test to make CI green.
- Fix the underlying cause. If a test reveals a real bug, fix the bug.
- PostgreSQL integration tests are marked `@pytest.mark.postgres` and auto-skipped when
  Docker is unavailable — they are **SKIPPED**, not PASSED.
- Record actual pass/fail/skip counts. Never claim tests passed without running them.

## 5. Human Approval Gate

- All **external write operations** (Jira, Slack, GitHub write, infrastructure changes) must:
  1. Be stored as a `ProposedAction` with `status=pending`.
  2. Require explicit approval by an authenticated, authorized user.
  3. Re-verify authorization at execution time.
  4. Create an immutable audit record on completion or rejection.
- No autonomous production changes, deployments, or destructive remediation.

## 6. Code Quality Floor

- Type annotations on all public functions and domain model fields.
- Pydantic v2 for all request/response/config validation.
- Ruff for lint and formatting (`ruff check .` and `ruff format --check .` must exit 0).
- mypy for type checking (`mypy app --ignore-missing-imports` must exit 0).
- No `except Exception` unless re-raising or logging at a boundary with full context.
- No unexplained magic values; use named constants or enums.
- Modules stay small and focused. No "god files." No duplicated business logic.

## 7. Database Safety

- **Alembic only** for schema management on the production path.
- `Base.metadata.create_all()` is permitted only in test fixtures (in-memory SQLite).
- Never silently drop columns or data. Write reversible `downgrade()` migrations.
- Document migration and rollback steps for every schema change.

## 8. Feature Theater Prohibition

- Every endpoint, button, and setting must work end-to-end or be explicitly labelled
  `[NOT YET IMPLEMENTED]` in the UI and return `501 Not Implemented` from the API.
- No fake charts, hard-coded success states, or simulated "connected" statuses.
- No fabricated benchmark numbers, incident data, or test results.

## 9. Observability & Error Handling

- Structured JSON logs in production; human-readable in development.
- Every request gets a correlation ID (`X-Request-ID`); propagate it through all log lines.
- Consistent error response shape: `{ "error": "<code>", "message": "...", "request_id": "..." }`.
- Database connection strings (with passwords) are never logged or returned in responses.

## 10. Docs Maintenance

Every phase must update:
- `README.md` — commands, repo map, troubleshooting
- `docs/ARCHITECTURE.md` — current implemented state
- `docs/BUILD_TRACKER.md` — phase status, date, test results, traceability
- `docs/decisions/ADR-NNNN-*.md` — one per significant technical decision

## 11. Generated Artifacts Never to Commit

```
backend/__pycache__/
backend/**/__pycache__/
backend/.pytest_cache/
backend/.mypy_cache/
backend/.ruff_cache/
backend/.coverage
backend/htmlcov/
backend/*.db
backend/*.db-shm
backend/*.db-wal
backend/.venv/
frontend/node_modules/
frontend/.next/
```

## 12. External Services

- If credentials are absent, use a **deterministic mock/local adapter** with clear labels.
- Never send real Slack messages, create real Jira tickets, or modify external accounts
  without explicit user confirmation.
- Real integration setup is documented, never assumed.

---

*Last updated: Phase 1 — Foundation Hardening*
