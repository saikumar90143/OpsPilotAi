"""Liveness/readiness probes and request correlation IDs."""

from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import get_db
from app.main import app

# Port 1 on loopback: a real, immediately refused connection (no mock).
UNREACHABLE_SECRET = "unreachable-s3cret"
UNREACHABLE_URL = f"postgresql+psycopg://probe:{UNREACHABLE_SECRET}@127.0.0.1:1/nodb"


def test_live_returns_ok(client: TestClient):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_ok_when_database_reachable(client: TestClient):
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": "ok"}}


def test_ready_returns_503_when_database_unreachable(client: TestClient):
    engine = create_engine(UNREACHABLE_URL, connect_args={"connect_timeout": 1})
    factory = sessionmaker(bind=engine)

    def broken_db() -> Iterator[Session]:
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = broken_db
    try:
        response = client.get("/health/ready")
    finally:
        engine.dispose()

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "checks": {"database": "unavailable"}}
    assert UNREACHABLE_SECRET not in response.text
    assert "127.0.0.1" not in response.text
    # Liveness is independent of the database.
    assert client.get("/health/live").status_code == 200


def test_request_id_generated_when_absent(client: TestClient):
    response = client.get("/health/live")
    request_id = response.headers["X-Request-ID"]
    assert len(request_id) == 32


def test_request_id_propagated_when_valid(client: TestClient):
    response = client.get("/health/live", headers={"X-Request-ID": "trace-abc.123_x"})
    assert response.headers["X-Request-ID"] == "trace-abc.123_x"


def test_request_id_replaced_when_malformed(client: TestClient):
    for bad in ("has spaces", "x" * 129, "bad<chars>", "semi;colon"):
        response = client.get("/health/live", headers={"X-Request-ID": bad})
        assert response.headers["X-Request-ID"] != bad
