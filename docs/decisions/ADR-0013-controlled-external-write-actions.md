# ADR-0013: Controlled External Write Actions & Human Approval Gate

- **Status:** Accepted (Phase 9)
- **Date:** 2026-11-21

## Context

Phase 9 introduces external write actions (creating Jira issues and posting Slack incident messages). Uncontrolled autonomous writes or model-controlled URLs/destinations pose severe security and operational risks.

## Decisions

1. **Human Approval Gate & State Machine (`proposed_actions`)**
   - Actions follow explicit states: `proposed` → `approved` → `executing` → `succeeded` / `failed` (or `rejected` / `expired`).
   - No action may execute without an explicit human `approve` transition and `ACTION_EXECUTE` permission.
   - At execution time, `action_service._reverify_execution_auth` re-queries `memberships` in the database so a user demoted or removed after approval cannot execute the action.

2. **Server-Side Allowlists & Payload-Hash Integrity**
   - `ExternalActionConnector` stores `allowed_targets_json` (Jira project keys or Slack channel IDs). Model- or client-provided arbitrary URLs, projects, or channels outside the allowlist are rejected (`422`).
   - `payload_hash` (SHA-256 of canonical `action_type`, `target_destination`, `payload_preview_json`) is computed at proposal time and re-verified at execution time to invalidate tampered payloads.

3. **Separation of Duties (MVP Policy)**
   - `ACTION_ALLOW_SELF_APPROVAL=false` by default: a human proposer cannot approve their own `ProposedAction`. AI-proposed actions (`requested_by_type="ai"`) may be approved by any authorized `ENGINEER`, `ADMIN`, or `OWNER`.
   - Approvals expire after `ACTION_DEFAULT_TTL_HOURS` (default 24h).

4. **Idempotent Execution & Safe Retries**
   - Every `ProposedAction` has a tenant-unique `idempotency_key`.
   - Re-executing a `succeeded` action returns the persisted `external_id` without calling the provider again. Transient timeouts retry up to `ACTION_MAX_EXECUTION_RETRIES` with the same `idempotency_key`.

5. **Mock vs. Live Distinction**
   - `MockJiraAdapter` and `MockSlackAdapter` operate deterministically offline and are clearly labelled `DEMO / MOCK`. Real Jira/Slack requests only occur when `mode="live"` and explicit credentials are configured.
