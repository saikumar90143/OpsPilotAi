# OpsPilot AI

An enterprise incident investigation and workflow automation platform. This repository starts with a working API foundation; integrations, the dashboard, and AI investigation workflows will be added in milestones.

## Current status

**Milestone 1 — Backend foundation**

- FastAPI application with interactive API docs.
- Incident create/list/retrieve/status-update endpoints.
- Pydantic request validation.
- SQLAlchemy persistence.
- SQLite mode for a zero-configuration first run.
- PostgreSQL mode through Docker Compose.
- Demo incident seed script.
- API tests using an isolated in-memory SQLite database.

## Requirements

- Python 3.11 or newer (the Docker image uses Python 3.12).
- pip.
- Optional: Docker Desktop for PostgreSQL mode.

## Run locally with SQLite (recommended for the first run)

From the repository root:

```bash
cd backend
python -m venv .venv
```

Activate the environment:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

Install dependencies and start the API:

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open these URLs:

- API documentation: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health
- Incident list: http://127.0.0.1:8000/api/v1/incidents

In a second terminal, activate the same virtual environment and seed demo data:

```bash
cd backend
python seed_demo.py
```

## Run with PostgreSQL using Docker

From the repository root:

```bash
docker compose up --build
```

The API will be available at http://127.0.0.1:8000/docs. PostgreSQL data is persisted in a Docker volume. The credentials in `docker-compose.yml` are for local development only; never reuse them in a public deployment.

To stop the services:

```bash
docker compose down
```

To also delete the local database volume:

```bash
docker compose down -v
```

## Run tests

From the repository root:

```bash
cd backend
pytest -q
```

## Create an incident through the API

```bash
curl -X POST http://127.0.0.1:8000/api/v1/incidents \
  -H "Content-Type: application/json" \
  -d '{"title":"Checkout API returns errors","description":"HTTP 500 rate increased after deployment.","service":"checkout-api","severity":"high","source":"manual"}'
```

On Windows PowerShell, use `curl.exe` or the interactive Swagger UI at `/docs`.

## Repository map

```text
opspilot-ai/
├── backend/
│   ├── app/
│   │   ├── api/incidents.py
│   │   ├── core/config.py
│   │   ├── core/database.py
│   │   ├── models/incident.py
│   │   ├── schemas/incident.py
│   │   └── main.py
│   ├── tests/test_incidents.py
│   ├── seed_demo.py
│   ├── Dockerfile
│   └── requirements.txt
├── docs/
│   ├── ARCHITECTURE.md
│   └── PRODUCT_REQUIREMENTS.md
├── docker-compose.yml
└── README.md
```

## Important production note

This is a learning and portfolio starter, not production-ready software yet. Before a real customer deployment, add authentication, tenant isolation, authorization checks, migrations, secrets management, rate limits, idempotent event ingestion, audit trails, backups, and security testing. Do not connect it to production systems until those controls are implemented and reviewed.
