"""Every error response uses {error, message, request_id} and matches X-Request-ID."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import SeededTenants, login_client


def _assert_envelope(response, status_code: int, error: str) -> dict:
    assert response.status_code == status_code
    body = response.json()
    assert body["error"] == error
    assert isinstance(body["message"], str) and body["message"]
    assert body["request_id"] == response.headers["X-Request-ID"]
    assert "detail" not in body
    return body


def test_unauthenticated_returns_401_envelope(client: TestClient):
    _assert_envelope(client.get("/api/v1/incidents"), 401, "unauthorized")


def test_domain_not_found(client: TestClient, tenants: SeededTenants):
    login_client(client, tenants.a_viewer.email)
    _assert_envelope(client.get("/api/v1/incidents/424242"), 404, "not_found")


def test_unknown_route(client: TestClient):
    _assert_envelope(client.get("/api/v1/does-not-exist"), 404, "not_found")


def test_method_not_allowed(client: TestClient, tenants: SeededTenants):
    headers = login_client(client, tenants.a_admin.email)
    response = client.delete("/api/v1/incidents", headers=headers)
    _assert_envelope(response, 405, "method_not_allowed")
    assert "allow" in {h.lower() for h in response.headers}


def test_validation_error_has_details_without_echoing_input(
    client: TestClient, tenants: SeededTenants
):
    headers = login_client(client, tenants.a_engineer.email)
    secret_like = "SECRET-PAYLOAD-VALUE"
    response = client.post(
        "/api/v1/incidents",
        json={"title": "ok title", "service": "svc", "severity": secret_like},
        headers=headers,
    )
    body = _assert_envelope(response, 422, "validation_error")
    assert body["details"][0]["loc"] == ["body", "severity"]
    assert secret_like not in response.text


def test_request_id_from_header_is_used_in_error_body(client: TestClient, tenants: SeededTenants):
    login_client(client, tenants.a_viewer.email)
    response = client.get("/api/v1/incidents/424242", headers={"X-Request-ID": "req-42"})
    assert response.json()["request_id"] == "req-42"


def test_unhandled_exception_returns_internal_error_envelope():
    crash_app: FastAPI = create_app()

    @crash_app.get("/boom")
    def boom() -> None:
        raise RuntimeError("internal detail that must not leak")

    with TestClient(crash_app) as crash_client:
        response = crash_client.get("/boom")
    body = _assert_envelope(response, 500, "internal_error")
    assert "must not leak" not in body["message"]
