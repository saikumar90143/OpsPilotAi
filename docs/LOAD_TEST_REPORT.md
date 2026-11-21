# OpsPilot AI — Load Test & Baseline Performance Report

**Date:** 2026-11-21  
**Script:** `scripts/load_test.py` (`backend\.venv\Scripts\python.exe scripts\load_test.py`)

---

## 1. Environment & Conditions

- **OS:** `Windows-10-10.0.19045-SP0`
- **Python:** `3.12.5`
- **CPU Cores:** `4`
- **Transport / Database:** In-process ASGI `TestClient(app)` against SQLite in-memory (`StaticPool`). Queue enqueue was stubbed in-process; worker event processing (`execute_event_processing`) was measured directly against SQLite. AI investigation used `MockInvestigationModel` (no external OpenAI network latency).
- *Note:* Production deployments over TCP to PostgreSQL + Redis + live OpenAI APIs will add network RTT and external LLM latency.

---

## 2. Measured Baseline Results

| Workload | Requests | Total (s) | Throughput (req/s) | p50 (ms) | p95 (ms) | Mean (ms) |
|---|---:|---:|---:|---:|---:|---:|
| `POST /api/v1/incidents` | 50 | 0.527 | 94.89 | 8.69 | 9.78 | 10.54 |
| `GET /api/v1/incidents?limit=20` | 100 | 0.921 | 108.61 | 8.83 | 11.26 | 9.21 |
| `POST /api/v1/webhooks/alertmanager` | 50 | 0.446 | 112.09 | 7.84 | 10.18 | 8.92 |
| `Worker execute_event_processing` | 50 | 0.180 | 278.19 | 3.44 | 6.45 | 3.59 |
| `POST /api/v1/incidents/1/investigations` (mock) | 20 | 0.546 | 36.64 | 25.23 | 31.22 | 27.29 |

---

## 3. Observed Bottlenecks & Notes

1. **AI Investigation (`25.23 ms` p50):** Dominated by LangGraph `StateGraph` compilation per invocation (`compiled = builder.compile()` in `app/ai/graph.py`) and 4 sequential read-only tool queries. In live OpenAI mode, external API RTT (`1–10s`) will dominate.
2. **OTel SQLAlchemy Instrumentation:** `opentelemetry-instrumentation-sqlalchemy 0.66b2` logs a version-range warning on `sqlalchemy 2.1.9` (`< 2.1.0` constraint) and skips automatic SQLAlchemy span wrapping; FastAPI HTTP, Celery worker, connector, and AI spans remain active.
