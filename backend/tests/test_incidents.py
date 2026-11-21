"""Incident API tests (in-memory SQLite, authenticated)."""

import pytest
from fastapi.testclient import TestClient

from tests.conftest import SeededTenants, login_client

EXPECTED_INCIDENT_FIELDS = {
    "id",
    "organization_id",
    "created_by_user_id",
    "assignee_user_id",
    "title",
    "description",
    "service",
    "environment",
    "severity",
    "status",
    "source",
    "external_source_id",
    "fingerprint",
    "metadata",
    "version",
    "affected_services",
    "tags",
    "acknowledged_at",
    "resolved_at",
    "closed_at",
    "archived_at",
    "created_at",
    "updated_at",
}


@pytest.fixture()
def eng_headers(client: TestClient, tenants: SeededTenants) -> dict[str, str]:
    return login_client(client, tenants.a_engineer.email)


def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_and_retrieve_incident(client: TestClient, eng_headers: dict[str, str]):
    payload = {
        "title": "Checkout API returns errors",
        "description": "HTTP 500 rate increased after deployment.",
        "service": "checkout-api",
        "severity": "high",
    }
    create_response = client.post("/api/v1/incidents", json=payload, headers=eng_headers)
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["title"] == payload["title"]
    assert created["status"] == "open"

    get_response = client.get(f"/api/v1/incidents/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["service"] == "checkout-api"


def test_rejects_invalid_severity(client: TestClient, eng_headers: dict[str, str]):
    response = client.post(
        "/api/v1/incidents",
        json={"title": "Invalid severity test", "service": "api", "severity": "urgent"},
        headers=eng_headers,
    )
    assert response.status_code == 422


def test_updates_incident_status(client: TestClient, eng_headers: dict[str, str]):
    create_response = client.post(
        "/api/v1/incidents",
        json={"title": "Worker queue delayed", "service": "worker", "severity": "medium"},
        headers=eng_headers,
    )
    incident_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/v1/incidents/{incident_id}/status",
        json={"status": "investigating"},
        headers=eng_headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "investigating"


# --- Compatibility & lifecycle tests --------------------------------------------


def _create(client: TestClient, headers: dict[str, str], title: str, **extra: str) -> dict:
    response = client.post(
        "/api/v1/incidents", json={"title": title, "service": "svc", **extra}, headers=headers
    )
    assert response.status_code == 201
    return response.json()


def test_legacy_health_body_unchanged(client: TestClient):
    assert client.get("/health").json() == {"status": "ok", "service": "opspilot-api"}


def test_response_field_set_unchanged(client: TestClient, eng_headers: dict[str, str]):
    created = _create(client, eng_headers, "Field set check")
    assert set(created) == EXPECTED_INCIDENT_FIELDS
    fetched = client.get(f"/api/v1/incidents/{created['id']}").json()
    assert set(fetched) == EXPECTED_INCIDENT_FIELDS


def test_defaults_applied(client: TestClient, eng_headers: dict[str, str]):
    created = _create(client, eng_headers, "Defaults check")
    assert created["severity"] == "medium"
    assert created["status"] == "open"
    assert created["source"] == "manual"
    assert created["description"] == ""
    assert created["archived_at"] is None


def test_list_returns_newest_first_and_respects_limit(
    client: TestClient, eng_headers: dict[str, str]
):
    for title in ("First incident", "Second incident", "Third incident"):
        _create(client, eng_headers, title)
    response = client.get("/api/v1/incidents", params={"limit": 2})
    assert response.status_code == 200
    assert [i["title"] for i in response.json()] == ["Third incident", "Second incident"]


def test_list_limit_bounds(client: TestClient, eng_headers: dict[str, str]):
    assert client.get("/api/v1/incidents", params={"limit": 0}).status_code == 422
    assert client.get("/api/v1/incidents", params={"limit": 101}).status_code == 422
    assert client.get("/api/v1/incidents", params={"limit": 100}).status_code == 200


def test_rejects_short_title(client: TestClient, eng_headers: dict[str, str]):
    response = client.post(
        "/api/v1/incidents", json={"title": "abc", "service": "svc"}, headers=eng_headers
    )
    assert response.status_code == 422


def test_rejects_invalid_status(client: TestClient, eng_headers: dict[str, str]):
    incident_id = _create(client, eng_headers, "Status validation")["id"]
    response = client.patch(
        f"/api/v1/incidents/{incident_id}/status",
        json={"status": "done"},
        headers=eng_headers,
    )
    assert response.status_code == 422


def test_get_unknown_incident_returns_404(client: TestClient, eng_headers: dict[str, str]):
    response = client.get("/api/v1/incidents/999999")
    assert response.status_code == 404
    assert response.json()["message"] == "Incident not found"


def test_patch_unknown_incident_returns_404(client: TestClient, eng_headers: dict[str, str]):
    response = client.patch(
        "/api/v1/incidents/999999/status", json={"status": "resolved"}, headers=eng_headers
    )
    assert response.status_code == 404


def test_archive_incident_soft_deletes_and_hides_from_queries(
    client: TestClient, tenants: SeededTenants
):
    admin_headers = login_client(client, tenants.a_admin.email)
    incident_id = _create(client, admin_headers, "To be archived")["id"]

    delete_resp = client.delete(f"/api/v1/incidents/{incident_id}", headers=admin_headers)
    assert delete_resp.status_code == 204
    assert client.get(f"/api/v1/incidents/{incident_id}").status_code == 404
    assert all(i["id"] != incident_id for i in client.get("/api/v1/incidents").json())
