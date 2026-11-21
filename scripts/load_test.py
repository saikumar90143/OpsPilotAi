"""Reproducible synthetic load test for OpsPilot AI core workflows.

Usage (from repository root):
    backend\\.venv\\Scripts\\python.exe scripts\\load_test.py
"""

import json
import logging
import os
import platform
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.investigations import ai_rate_limiter
from app.api.v1.webhooks import get_enqueue_fn, webhook_rate_limiter
from app.core.database import Base, get_db
from app.core.permissions import Role
from app.core.security import hash_password
from app.core.secrets import SIGNATURE_HEADER, sign_webhook_payload
from app.integrations.alertmanager import AlertEventStatus, build_sample_alertmanager_payload
from app.main import app
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.user import User
from app.services import ingestion_service


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, int(round((pct / 100.0) * (len(sorted_vals) - 1))))
    return round(sorted_vals[idx], 2)


def _measure(label: str, n: int, fn) -> dict[str, object]:
    latencies_ms: list[float] = []
    t_start = time.perf_counter()
    for i in range(n):
        t0 = time.perf_counter()
        fn(i)
        latencies_ms.append((time.perf_counter() - t0) * 1000.0)
    total_s = time.perf_counter() - t_start
    latencies_ms.sort()
    return {
        "workload": label,
        "requests": n,
        "total_seconds": round(total_s, 3),
        "throughput_rps": round(n / total_s, 2),
        "p50_ms": _percentile(latencies_ms, 50),
        "p95_ms": _percentile(latencies_ms, 95),
        "mean_ms": round(statistics.mean(latencies_ms), 2),
    }


def main() -> None:
    logging.disable(logging.WARNING)
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False)

    with SessionLocal() as db:
        org = Organization(name="Load Org", slug="load-org")
        user = User(
            email="load@opspilot.local",
            full_name="Load User",
            password_hash=hash_password("LoadPass123!"),
        )
        db.add_all([org, user])
        db.flush()
        db.add(Membership(organization_id=org.id, user_id=user.id, role=Role.ADMIN.value))
        db.commit()

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_enqueue_fn] = lambda: (lambda event_id, corr_id: None)

    results = []
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "load@opspilot.local", "password": "LoadPass123!"},
        )
        assert login.status_code == 200
        csrf = client.cookies.get("opspilot_csrf") or ""
        headers = {"X-CSRF-Token": csrf}

        integ = client.post(
            "/api/v1/integrations",
            headers=headers,
            json={"provider": "alertmanager", "name": "Load AM", "is_simulator_mode": False},
        ).json()
        secret = integ["signing_secret"]
        hook_path = integ["webhook_path"]

        # 1. Incident create + list
        def create_inc(i: int) -> None:
            r = client.post(
                "/api/v1/incidents",
                headers=headers,
                json={
                    "title": f"Load incident {i}",
                    "description": "Synthetic load test",
                    "service": "checkout-api",
                    "environment": "production",
                    "severity": "medium",
                },
            )
            assert r.status_code == 201

        results.append(_measure("POST /api/v1/incidents", 50, create_inc))
        results.append(
            _measure(
                "GET /api/v1/incidents",
                100,
                lambda i: client.get("/api/v1/incidents?limit=20").raise_for_status(),
            )
        )

        # 2. Webhook ingestion
        def ingest_hook(i: int) -> None:
            webhook_rate_limiter.reset()
            payload = build_sample_alertmanager_payload(
                scenario="high_error_rate", status=AlertEventStatus.FIRING
            )
            payload["alerts"][0]["fingerprint"] = f"fp-load-{i}"
            raw = json.dumps(payload).encode("utf-8")
            sig = sign_webhook_payload(raw, secret)
            r = client.post(
                hook_path,
                content=raw,
                headers={"Content-Type": "application/json", SIGNATURE_HEADER: sig},
            )
            assert r.status_code == 202

        results.append(_measure("POST /api/v1/webhooks/alertmanager", 50, ingest_hook))

        # 3. Queue event processing (direct service execution)
        def process_event(i: int) -> None:
            with SessionLocal() as db:
                ingestion_service.execute_event_processing(db, event_id=i + 1)

        results.append(_measure("Worker execute_event_processing", 50, process_event))

        # 4. Mock AI investigation
        def run_ai(i: int) -> None:
            ai_rate_limiter.reset()
            r = client.post(
                "/api/v1/incidents/1/investigations",
                headers=headers,
                json={"window_hours": 24},
            )
            assert r.status_code == 201

        results.append(_measure("POST /api/v1/incidents/1/investigations (mock)", 20, run_ai))

    app.dependency_overrides.clear()
    engine.dispose()

    output = {
        "environment": {
            "os": platform.platform(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "database": "SQLite in-memory (StaticPool, in-process ASGI TestClient)",
        },
        "benchmarks": results,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
