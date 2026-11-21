# Runbook: Security Incident Response

## 1. Suspected Credential or Token Compromise
1. **JWT Signing Key (`JWT_SECRET_KEY`):** Rotate `JWT_SECRET_KEY` in `.env` and restart `api` + `worker` to invalidate all active access tokens immediately.
2. **Integration Encryption Key (`INTEGRATION_ENCRYPTION_KEY`):** Re-encrypt or rotate tenant webhook secrets (`POST /api/v1/integrations/{id}/rotate-secret`) and replace GitHub/Jira/Slack tokens in `/settings`.
3. **User Session Compromise:** Revoke refresh tokens by demoting/removing the affected membership or resetting the user's password.

## 2. Forensics & Audit Verification
- Query `GET /api/v1/audit-logs` (as Owner/Admin) and filter structured JSON logs by `request_id` (`X-Request-ID`) and `trace_id`.
- Check `proposed_actions` and `investigation_runs` for any unauthorized proposals or executions.
