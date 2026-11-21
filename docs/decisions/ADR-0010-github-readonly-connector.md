# ADR-0010 — Read-Only GitHub Evidence Connector

**Status:** Accepted  
**Date:** 2026-11-21  
**Phase:** Phase 6 — GitHub Read-Only Connector

---

## Context

During incident triage, engineers need recent commits, pull requests, reviews, and deployments
correlated with the affected service and incident time window. Granting write scopes or
conflating correlation with root-cause proof introduces security and operational risk.

## Decisions

1. **Strict read-only scope:** `SourceControlProvider` exposes only read operations
   (`test_connection`, `get_repository`, `list_commits`, `list_pull_requests`,
   `list_deployments`). `GitHubClient` only issues `GET` requests (plus the single installation
   token exchange `POST /app/installations/{id}/access_tokens`).
2. **Auth modes:** GitHub App installation (RS256 JWT + short-lived installation token) is
   preferred for production; fine-grained read-only PAT is supported for local development.
   Credentials and webhook secrets are encrypted at rest with Fernet and never logged or returned.
3. **Resilience:** `GitHubClient` uses `If-None-Match` / `ETag` caching (`304`), `Link` header
   pagination, `X-RateLimit-*` detection, and bounded exponential backoff retries.
4. **Correlation as hypothesis:** `POST /api/v1/incidents/{id}/correlate-github` attaches
   attributed `EvidenceRef` records explicitly labelled `hypothesis: true` with
   `"Correlation hypothesis only — time/service proximity is not proof of causation."`
5. **Mock parity & honest UI:** `MockGitHubAdapter` provides deterministic local fixtures
   marked `DEMO / MOCK` in both API metadata and UI badges, distinct from `LIVE`.
