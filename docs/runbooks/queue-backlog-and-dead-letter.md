# Runbook: Queue Backlog & Dead-Letter Growth

**Alerts:** `OpsPilotQueueBacklogHigh`, `OpsPilotDeadLetterGrowth`

## Symptoms
- `opspilot_queue_depth{status=~"pending|retrying"}` stays above 50.
- `opspilot_queue_dead_letters_total` increases.

## Triage Steps
1. Inspect `docker compose ps` (`redis` and `worker` health).
2. Open **Ingestion & Events** (`/events`) or query `GET /api/v1/events?status=dead_letter` as Admin.
3. Correlate `correlation_id` (`X-Request-ID`) and `trace_id` in structured API/worker logs.

## Safe Mitigation
- Fix transient downstream or DB issues, then use **Replay** (`POST /api/v1/events/{id}/replay`) as Admin.
