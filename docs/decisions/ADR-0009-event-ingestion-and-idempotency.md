# ADR-0009 — Event Ingestion, Webhook Auth, Idempotency, and Redis/Celery Queue

**Status:** Accepted  
**Date:** 2026-11-21  
**Phase:** Phase 4 — Webhook Ingestion & Background Queue

---

## Context

Alert ingestion must never drop accepted webhooks, must deduplicate retries without creating
duplicate incidents or timeline entries, must protect inbound endpoints from forgery/replay/abuse,
and must isolate simulator events from live provider connections.

## Decisions

1. **Persist before enqueue:** `InboundEvent` receipts are committed (`status=received`) in
   PostgreSQL/SQLite **before** dispatching to Redis/Celery. If Redis is unavailable, the API
   returns `503` while retaining the persisted receipt for admin inspection and replay.
2. **Idempotency & deterministic deduplication:**
   - Inbound receipts are keyed uniquely by `(organization_id, provider, idempotency_key)`.
   - Incident deduplication links firing/resolved alerts to the active non-closed incident for
     `(organization_id, fingerprint)`.
3. **Webhook auth & rotation:**
   - Primary: `X-OpsPilot-Signature: t=<unix_ts>,v1=<hmac_sha256_hex>` over `f"{ts}.{raw_body}"`
     with `±300s` replay protection.
   - Fallback: `Authorization: Bearer <secret>` for providers (such as stock Alertmanager) that
     cannot compute HMAC body signatures. Limits are documented in `docs/SECURITY.md`.
   - Secrets are encrypted at rest with Fernet (`INTEGRATION_ENCRYPTION_KEY`) and support
     zero-downtime rotation via a time-bounded grace window.
4. **Bounded retries & dead-letter:** Transient worker errors retry with exponential backoff
   + jitter up to `max_attempts` (default 3); poison payloads or exhausted retries transition
   to `dead_letter` and write an `AuditLog` event.
5. **Simulator honesty:** Simulator-mode integrations report `connection_status="simulator"`
   (never `"connected"`) and tag created incidents with `source="alertmanager-simulator"` and
   `metadata.simulated=True`.
