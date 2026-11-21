# Runbook: Backup, Restore & Disaster Recovery (PostgreSQL & Redis)

## 1. Data Durability Architecture
- **PostgreSQL (System of Record):** Stores all tenants, users, incidents, audit logs, `inbound_events` receipts, knowledge documents, AI investigation runs, and `proposed_actions`.
- **Redis (Ephemeral Queue & Broker):** Used by Celery as the task transport. Inbound webhooks are persisted to `inbound_events` in PostgreSQL **before** enqueueing to Redis. If Redis restarts or loses in-flight messages, no webhook payload is lost — Admins can replay `received`/`failed`/`dead_letter` events via `/events` or `POST /api/v1/events/{id}/replay`.

## 2. PostgreSQL Backup (`pg_dump`)
```bash
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom > backup_$(date +%Y%m%d_%H%M%S).dump
```

## 3. PostgreSQL Restore (`pg_restore`)
```bash
docker compose stop api worker
docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists < backup_YYYYMMDD_HHMMSS.dump
docker compose up -d api worker
```

## 4. RPO / RTO Notes
- **RPO:** Determined by `pg_dump` / WAL archiving cadence (e.g. 24h for daily `pg_dump`, < 5m with continuous WAL archiving).
- **RTO:** ~5–15 minutes for container recreation + `pg_restore` + `alembic upgrade head`.
