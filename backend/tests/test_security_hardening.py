"""Phase 11 negative security tests: SSRF, headers, IDOR/BOLA, RBAC, CSRF, oversized payloads."""

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.errors import RateLimitedError
from app.core.rate_limit import RateLimiter
from tests.conftest import TEST_PASSWORD, login_client


def test_security_response_headers_and_ssrf_guard(client: TestClient, tenants):
    admin_headers = login_client(client, "admin@acme.local", TEST_PASSWORD)

    health = client.get("/health/live")
    assert health.status_code == 200
    assert health.headers.get("X-Content-Type-Options") == "nosniff"
    assert health.headers.get("X-Frame-Options") == "DENY"
    assert health.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    api_res = client.get("/api/v1/incidents")
    assert api_res.status_code == 200
    assert api_res.headers.get("Cache-Control") == "no-store"

    for bad_url in (
        "http://example.com",
        "https://127.0.0.1:8000",
        "https://169.254.169.254/latest/meta-data",
        "https://10.0.0.5",
        "https://localhost/jira",
    ):
        resp = client.post(
            "/api/v1/action-connectors",
            headers=admin_headers,
            json={
                "provider": "jira",
                "name": f"Bad {bad_url}",
                "mode": "live",
                "base_url": bad_url,
                "allowed_targets": ["OPS"],
                "credential": "dummy-token",
            },
        )
        assert resp.status_code == 422, (
            f"Expected 422 for SSRF URL {bad_url}, got {resp.status_code}"
        )


def test_idor_privilege_escalation_csrf_and_oversized_webhook(client: TestClient, tenants):
    # 1. Privilege escalation: Viewer cannot write, manage, or approve; Admin cannot update org
    viewer_headers = login_client(client, "viewer@acme.local", TEST_PASSWORD)
    assert (
        client.post(
            "/api/v1/incidents",
            headers=viewer_headers,
            json={
                "title": "Viewer attempt",
                "description": "Should fail",
                "service": "api",
                "environment": "production",
                "severity": "low",
            },
        ).status_code
        == 403
    )

    admin_headers = login_client(client, "admin@acme.local", TEST_PASSWORD)
    assert (
        client.patch(
            "/api/v1/organizations/current",
            headers=admin_headers,
            json={"name": "Hijacked Org"},
        ).status_code
        == 403
    )

    # 2. CSRF missing on cookie-authenticated POST -> 403
    assert (
        client.post(
            "/api/v1/incidents",
            json={
                "title": "No CSRF",
                "description": "Should fail",
                "service": "api",
                "environment": "production",
                "severity": "low",
            },
        ).status_code
        == 403
    )

    # 3. Create incident in Org A, verify IDOR from Org B returns 404
    inc_a = client.post(
        "/api/v1/incidents",
        headers=admin_headers,
        json={
            "title": "Acme Private Incident",
            "description": "Confidential",
            "service": "checkout-api",
            "environment": "production",
            "severity": "high",
        },
    ).json()["id"]

    # Create an integration in Org A for oversized webhook test
    integ = client.post(
        "/api/v1/integrations",
        headers=admin_headers,
        json={"provider": "alertmanager", "name": "Size Test", "is_simulator_mode": False},
    ).json()

    # Oversized webhook body (> 256 KiB default) rejected with 413
    oversized = b"{" + b'"pad":"' + (b"x" * (Settings().webhook_max_bytes + 1024)) + b'"}'
    hook_resp = client.post(
        integ["webhook_path"],
        content=oversized,
        headers={"Content-Type": "application/json"},
    )
    assert hook_resp.status_code == 413

    # Cross-tenant IDOR check from Org B
    login_client(client, "owner@beta.local", TEST_PASSWORD)
    assert client.get(f"/api/v1/incidents/{inc_a}").status_code == 404
    assert client.get(f"/api/v1/incidents/{inc_a}/timeline").status_code == 404
    assert client.get(f"/api/v1/incidents/{inc_a}/actions").status_code == 404


def test_rate_limiter_enforces_limit_and_cannot_be_bypassed():
    limiter = RateLimiter()
    for _ in range(3):
        limiter.check("org1:user1", max_requests=3, window_seconds=60)
    try:
        limiter.check("org1:user1", max_requests=3, window_seconds=60)
        raise AssertionError("Expected RateLimitedError")
    except RateLimitedError:
        pass
