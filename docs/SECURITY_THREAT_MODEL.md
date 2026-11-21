# OpsPilot AI — Security Threat Model & Hardening Findings

**Date:** 2026-11-21  
**Scope:** Phases 1–11 (FastAPI backend, Celery worker, Next.js frontend, Docker Compose)  
**Disclaimer:** This is an engineering threat model aligned with OWASP ASVS / API Security Top 10 practices; it is **not** a formal compliance certification or third-party penetration test.

---

## 1. Threat Model & Controls

| Area | Primary Threats | Implemented Controls |
|---|---|---|
| **Auth & Sessions** | Credential stuffing, token theft, session fixation | Argon2id password hashing; short-lived JWTs in `HttpOnly` `SameSite=Lax` cookies; rotating opaque refresh tokens with reuse-detection family revocation; sliding-window auth rate limiting. |
| **Tenant Isolation & IDOR/BOLA** | Cross-tenant data access or forged `organization_id` | `organization_id` derived exclusively from verified server-side session/membership; every domain query filters by `organization_id`; cross-tenant lookups return `404`. |
| **RBAC & Privilege Escalation** | Viewer mutating state; Admin promoting self to Owner | Server-side `require_permission(...)` on every endpoint; DB membership & permission re-verified at action execution time (`_reverify_execution_auth`). |
| **CSRF & CORS** | Cross-site state-changing requests | Double-submit `X-CSRF-Token` enforced on cookie-authenticated `POST`/`PATCH`/`DELETE`; narrow CORS `FRONTEND_ORIGIN`. |
| **SSRF** | Malicious connector `base_url` targeting localhost/metadata/RFC1918 | `validate_safe_outbound_url` (`app/core/ssrf.py`) enforces `https://` and blocks loopback, link-local (`169.254.0.0/16`), RFC1918, and `.local`/`.internal` hosts. |
| **File Uploads (KB)** | Malicious executables, path traversal, oversized payloads | Strict `.md`/`.txt` + MIME allowlist, `512 KiB` cap, filename sanitization, NUL-byte & magic-header (`MZ`, `ELF`, `%PDF-`, `PK`) rejection, UTF-8 validation. *(Limitation: no external AV daemon bundled.)* |
| **Webhooks** | Spoofing, replay, payload floods | Constant-time HMAC-SHA256 (`X-OpsPilot-Signature`, `X-Hub-Signature-256`), timestamp replay window (`300s`), idempotency keys, `256 KiB` body cap (`413`). |
| **AI Prompt Injection & Tools** | Untrusted logs/KB overriding instructions; fabricated citations; arbitrary SQL/shell | Fixed 4-tool read-only allowlist (no SQL/shell/HTTP); untrusted-data framing; strict `validate_report_citations` rejecting unknown `evidence_id`s; per-tenant daily quota. |
| **External Write Actions** | Unapproved Jira/Slack writes, payload tampering, self-approval | Mandatory human approval gate (`ProposedAction`), separation of duties (`ACTION_ALLOW_SELF_APPROVAL=false`), destination allowlists, `payload_hash` integrity check, idempotent execution. |
| **Secrets & Logs** | Credential leakage in logs, responses, or DB | Fernet-encrypted integration secrets; `repr=False` on secret settings; `redact()`/`redact_text()` on logs, ingested application logs, and error strings. |

---

## 2. Phase 11 Findings & Remediations

| ID | Severity | Finding | Status |
|---|---|---|---|
| **SEC-11-01** | High | `ActionConnectorCreate.base_url` checked `https://` prefix only, leaving potential SSRF to `https://127.0.0.1` or `https://169.254.169.254`. | **Fixed** (`app/core/ssrf.py` + `schemas/action.py` + negative tests in `test_security_hardening.py`) |
| **SEC-11-02** | Medium | API responses lacked explicit `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and `Cache-Control: no-store` headers. | **Fixed** (`app/api/middleware.py` + negative tests) |
| **SEC-11-03** | Low | `RateLimiter` is in-memory per API process; multi-replica production deployments should back rate limiting with Redis. | **Documented** (acceptable for single-instance MVP; tracked for scale-out) |
