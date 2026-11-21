# Runbook: Connector Rate Limits & AI Investigation Timeouts

**Alert:** `OpsPilotAIInvestigationFailureRate`

## Symptoms
- `opspilot_connector_requests_total{outcome=~"error|timeout|rate_limited"}` rises.
- `opspilot_ai_investigation_duration_seconds_count{status="failed"}` rises.

## Triage Steps
1. Check `GET /api/v1/ai/status` and connector `last_error` in `/settings`.
2. Inspect `investigation_tool_calls` for `timeout` or `error` statuses.
3. Verify `OPENAI_MODEL` / `OPENAI_API_KEY` or switch `AI_PROVIDER_MODE=mock` for safe degraded operation.
