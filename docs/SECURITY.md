# OpsPilot AI — Security Architecture, Permission Matrix & Frontend Auth Contract

**Last updated:** Phase 2 — Multi-Tenant Identity & RBAC (2026-11-21)

---

## 1. Roles & Permission Matrix

Every authenticated request resolves `AuthContext(user, organization, role)` from the signed
access token **and** re-queries the active `memberships` row in the database so role demotions
or membership removals take effect immediately.

| Action / Endpoint | `OWNER` | `ADMIN` | `ENGINEER` | `VIEWER` |
|---|---|---|---|---|
| `GET /health/live`, `GET /health/ready` | Public | Public | Public | Public |
| `POST /api/v1/auth/login`, `/refresh`, `/logout`, `/accept-invite` | Public/Session | Public/Session | Public/Session | Public/Session |
| `GET /api/v1/auth/me` | ✅ | ✅ | ✅ | ✅ |
| `GET /api/v1/organizations/current` | ✅ | ✅ | ✅ | ✅ |
| `PATCH /api/v1/organizations/current` | ✅ | ❌ | ❌ | ❌ |
| `GET /api/v1/memberships` | ✅ | ✅ | ✅ | ✅ |
| `POST /api/v1/invitations` (`admin` / `engineer` / `viewer`) | ✅ | ✅ | ❌ | ❌ |
| `GET /api/v1/invitations`, `DELETE /api/v1/invitations/{id}` | ✅ | ✅ | ❌ | ❌ |
| `PATCH /api/v1/memberships/{id}/role` (`engineer` / `viewer`) | ✅ | ✅ | ❌ | ❌ |
| `PATCH /api/v1/memberships/{id}/role` (`admin` / `owner` transfer) | ✅ | ❌ | ❌ | ❌ |
| `DELETE /api/v1/memberships/{id}` (`engineer` / `viewer`) | ✅ | ✅ | ❌ | ❌ |
| `DELETE /api/v1/memberships/{id}` (`admin`) | ✅ | ❌ | ❌ | ❌ |
| `GET /api/v1/audit-logs` | ✅ | ✅ | ❌ | ❌ |
| `GET /api/v1/incidents`, `GET /api/v1/incidents/{id}` | ✅ | ✅ | ✅ | ✅ |
| `POST /api/v1/incidents`, `PATCH /api/v1/incidents/{id}/status` | ✅ | ✅ | ✅ | ❌ |
| `DELETE /api/v1/incidents/{id}` (soft-delete / archive) | ✅ | ✅ | ❌ | ❌ |

---

## 2. Browser Token Storage, Cookie/CSRF Strategy & CORS

### Why `HttpOnly` Cookies Instead of `localStorage`
Tokens stored in `localStorage` or `sessionStorage` are readable by any JavaScript running on the
origin (XSS). OpsPilot AI stores session tokens exclusively in **`HttpOnly` cookies**:

| Cookie | `HttpOnly` | `SameSite` | `Path` | `Secure` | Lifetime |
|---|---|---|---|---|---|
| `opspilot_access` | `true` | `Lax` | `/` | `true` in prod | 15 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`) |
| `opspilot_refresh` | `true` | `Lax` | `/api/v1/auth` | `true` in prod | 7 days (`REFRESH_TOKEN_EXPIRE_DAYS`) |
| `opspilot_csrf` | `false` | `Lax` | `/` | `true` in prod | Matches refresh cookie |

- Scoping `opspilot_refresh` to `/api/v1/auth` prevents the refresh credential from being sent on
  ordinary `/api/v1/incidents` requests.
- **Double-submit CSRF protection:** Every cookie-authenticated state-changing request
  (`POST`, `PUT`, `PATCH`, `DELETE`) must send `X-CSRF-Token` matching the `opspilot_csrf`
  cookie (verified with `hmac.compare_digest`). Public entry points (`/auth/login`,
  `/auth/accept-invite`) are protected by `SameSite=Lax`, narrow CORS, and rate limiting.
- **Narrow CORS:** `allow_origins=[FRONTEND_ORIGIN]`, `allow_credentials=True`, explicit
  `allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"]`, explicit
  `allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID", "Authorization"]`.

---

## 3. Frontend Auth Contract (for Phase 3)

1. All browser `fetch` / API client calls **must** set `credentials: "include"` and **must never**
   read or store JWTs in `localStorage` or `sessionStorage`.
2. For `POST` / `PATCH` / `DELETE` requests, read the `opspilot_csrf` cookie in memory and attach
   it as the `X-CSRF-Token` header.
3. On `401` responses from API endpoints, attempt a single `POST /api/v1/auth/refresh` (with
   `X-CSRF-Token`); if refresh fails, redirect to `/login`.
4. Never send `organization_id` or `role` to try to switch tenants or escalate privileges —
   all request schemas forbid unexpected fields (`extra="forbid"`) and the backend ignores any
   client-supplied tenant context.

---

## 4. Threat Notes & Security Assumptions

- **Password hashing:** Argon2id via `argon2-cffi`. Login errors return a uniform
  `401 "Invalid email or password"` regardless of whether the email exists.
- **Refresh token rotation & reuse detection:** Refresh tokens are 32-byte random opaque tokens
  stored hashed (`SHA-256`) with a `family_id`. Presenting a rotated/revoked token triggers
  immediate revocation of the entire `family_id` and records `auth.refresh.reuse_detected`.
- **Cross-tenant IDOR prevention:** All repository queries require `organization_id: int`.
  Cross-tenant lookups return `404 Not Found` (never `403`) to prevent resource existence
  inference.
- **Rate limiting:** Sliding-window per-IP rate limiting protects `/auth/login`, `/auth/refresh`,
  and `/auth/accept-invite` (`429 rate_limited`). Current limiter is process-local memory;
  Phase 4 moves this behind Redis for multi-worker deployments.
- **Local bootstrap:** `python -m app.bootstrap` is CLI-only, refuses to run when
  `APP_ENV=production`, and generates a random local password if `BOOTSTRAP_DEMO_PASSWORD` is
  unset. Public self-registration is disabled; users join only via signed invitation tokens.
- **Audit trail:** `audit_logs` is append-only and sanitizes sensitive keys (`password`,
  `password_hash`, `token`, `refresh_token`, URLs with credentials) before persistence.
- **Webhook authentication & limits:**
  - `POST /api/v1/webhooks/alertmanager/{endpoint_token}` verifies `X-OpsPilot-Signature`
    (`t=<ts>,v1=<hmac_sha256>`) with a `±300s` replay window and Fernet-encrypted secrets
    supporting dual-key rotation grace periods.
  - For providers that cannot compute HMAC body signatures (e.g., stock Alertmanager),
    `Authorization: Bearer <secret>` is accepted as a fallback; this relies on TLS in
    transit and does not provide per-body integrity or timestamp replay protection.
  - Inbound webhooks enforce `WEBHOOK_MAX_BYTES` (`256 KB` → `413`) and per-endpoint rate
    limits (`429`).
