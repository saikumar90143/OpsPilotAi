# Runbook: API Error Spike & Database Connectivity

**Alert:** `OpsPilotHighAPIErrorRate`

## Symptoms
- `opspilot_http_errors_total{status_class="5xx"}` > 5% of total requests.
- `/health/ready` returns `503`.

## Triage Steps
1. Check `/health/ready` and `docker compose logs api --tail=100`.
2. Search structured JSON logs by `request_id` and `trace_id` for database timeouts or pool exhaustion.
3. Verify PostgreSQL health (`pg_isready`).
