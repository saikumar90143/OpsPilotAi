# ADR-0003 — Use pydantic-settings for Application Configuration

**Status:** Accepted  
**Date:** 2026-11-20  
**Phase:** Phase 1 — Foundation Hardening

---

## Context

The starter codebase read configuration values using raw `os.getenv()` calls with string defaults:

```python
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./opspilot.db")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
```

This approach has several problems:
- **No type safety** — all values are strings; a numeric `PORT` env var requires manual `int()` casting.
- **No validation** — an invalid `DATABASE_URL` or a missing required secret is not caught until
  the first database operation fails at runtime.
- **No IDE support** — there is no documented contract of what configuration the application expects.
- **No `.env` file support** — developers must manually export variables in every shell session.
- **Secrets can leak** — there is no built-in mechanism to prevent `DATABASE_URL` (which contains a
  password) from appearing in `repr()` output or log lines.

---

## Decision

Use **`pydantic-settings`** (`pydantic_settings.BaseSettings`) to define a typed, validated
`Settings` class. Specifically:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "OpsPilot AI API"
    app_env: Literal["development", "testing", "production"] = "development"
    database_url: str  # Required; no default forces explicit configuration
    ...
```

A singleton `settings = Settings()` is instantiated at module import time. All other modules import
`settings` from `app.core.config` — no other module reads from `os.environ` directly.

Secret fields (passwords, tokens, keys) use Pydantic's `SecretStr` type, which redacts the value in
`repr()` and prevents accidental printing, while still allowing the actual value to be retrieved
with `.get_secret_value()` when needed.

---

## Consequences

**Positive:**
- Configuration validation at startup — misconfigured environments fail immediately with a clear error.
- Type-safe access — `settings.database_url` is a `str`, not `Optional[str]`.
- `.env` file support — no manual `export` commands in development.
- SecretStr prevents password leakage in logs and stack traces.
- Clear documented contract of all configuration keys in one file.
- IDE completion works correctly.

**Negative / Trade-offs:**
- One extra dependency (`pydantic-settings`).
- `Settings()` is instantiated at import time — tests that need different settings must use
  `monkeypatch.setenv` or override the `settings` object before the module is imported.
  (Mitigation: `conftest.py` fixtures handle this cleanly.)

---

## Alternatives Considered

### Keep `os.getenv()` (Rejected)
No path to the validation and secret-safety benefits without significant custom code.

### Use `dynaconf` (Rejected)
More powerful but heavier than needed. `pydantic-settings` integrates with our existing Pydantic v2
dependency and covers all current requirements.

### Use environment variables only (no `.env`) (Rejected)
Acceptable in production (where environment variables are injected by the platform), but creates
friction for local development where developers must manage many variables manually.

---

## Review Trigger

Re-evaluate if `pydantic-settings` does not support a required configuration source
(e.g., Vault integration, AWS Secrets Manager) in a future phase.
