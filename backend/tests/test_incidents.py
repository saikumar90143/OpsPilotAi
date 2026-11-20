"""API tests use an isolated in-memory SQLite database."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app

TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(bind=TEST_ENGINE, autoflush=False, autocommit=False)


@pytest.fixture()
def client():
    Base.metadata.create_all(bind=TEST_ENGINE)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=TEST_ENGINE)


def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_and_retrieve_incident(client: TestClient):
    payload = {
        "title": "Checkout API returns errors",
        "description": "HTTP 500 rate increased after deployment.",
        "service": "checkout-api",
        "severity": "high",
    }
    create_response = client.post("/api/v1/incidents", json=payload)
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["title"] == payload["title"]
    assert created["status"] == "open"

    get_response = client.get(f"/api/v1/incidents/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["service"] == "checkout-api"


def test_rejects_invalid_severity(client: TestClient):
    response = client.post(
        "/api/v1/incidents",
        json={"title": "Invalid severity test", "service": "api", "severity": "urgent"},
    )
    assert response.status_code == 422


def test_updates_incident_status(client: TestClient):
    create_response = client.post(
        "/api/v1/incidents",
        json={"title": "Worker queue delayed", "service": "worker", "severity": "medium"},
    )
    incident_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/v1/incidents/{incident_id}/status",
        json={"status": "investigating"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "investigating"
