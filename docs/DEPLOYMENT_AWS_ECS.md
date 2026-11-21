# Cloud Deployment Architecture (AWS ECS Fargate) & Low-Cost Alternative

> **Important:** The Terraform blueprint in `infra/aws-ecs-fargate/` is provided for architecture review only. **Do not run `terraform apply`** unless you intend to provision AWS resources and incur charges.

---

## 1. Architecture Overview
- **Edge & TLS:** Public HTTPS Application Load Balancer (ACM TLS certificate) forwarding to private ECS Fargate tasks (`/health/ready` health check).
- **Compute:** ECS Fargate cluster running `api` (FastAPI/Uvicorn), `worker` (Celery), `frontend` (Next.js), and a one-shot `migrate` task (`alembic upgrade head`).
- **Data & Secrets:** RDS PostgreSQL 16 (encrypted, automated 7-day backups), ElastiCache Redis 7 (ephemeral Celery broker), AWS Secrets Manager (`DATABASE_URL`, `JWT_SECRET_KEY`, `INTEGRATION_ENCRYPTION_KEY`, `OPENAI_API_KEY`), and CloudWatch Logs.

## 2. Deployment, Migration Order & Rollback
1. **Migrate first:** Run the one-shot `migrate` ECS task (`alembic upgrade head`) before updating the `api` or `worker` service revisions.
2. **Rolling deploy:** Update `api`, `worker`, and `frontend` ECS services with `minimum_healthy_percent = 100` and `/health/ready` ALB checks.
3. **Rollback:** Register the previous task definition revision in ECS; if a schema change must be reverted, run `alembic downgrade -1` (all migrations `0001`–`0008` include tested `downgrade()` steps).

## 3. Cost Considerations & Teardown
- **Estimated AWS Monthly Cost (staging baseline):** ~\$70–\$110/month (2× small Fargate tasks ~\$30, `db.t4g.micro` ~\$15, `cache.t4g.micro` ~\$12, ALB ~\$18, CloudWatch/Secrets ~\$5).
- **Teardown:** Disable RDS `deletion_protection` if needed, then run `terraform destroy` inside `infra/aws-ecs-fargate/`.

## 4. Low-Cost Demo Alternative
For portfolio/recruiter demos without AWS charges, run the complete stack locally with Docker Compose:
```bash
Copy-Item .env.example .env   # set POSTGRES_PASSWORD
docker compose --profile demo up --build -d
```
Or deploy onto a single \$5–\$10/month VPS using the same `docker-compose.yml` behind Caddy/Nginx TLS.
