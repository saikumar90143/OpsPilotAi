"""Read-only GitHub connector tests: mock adapter, HTTP client mocks, webhooks, correlation."""

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

import httpx2 as httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.core.secrets import GITHUB_SIGNATURE_HEADER
from app.integrations.scm.base import (
    ScmAuthType,
    ScmPermissionError,
    ScmRateLimitError,
)
from app.integrations.scm.github_client import GitHubClient
from tests.conftest import SeededTenants, login_client


def _test_rsa_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


def test_mock_github_connector_and_correlation_with_hypothesis_disclaimer(
    client: TestClient, tenants: SeededTenants
):
    admin_headers = login_client(client, tenants.a_admin.email)
    conn_resp = client.post(
        "/api/v1/github/connectors",
        json={
            "name": "Acme Demo GitHub",
            "mode": "mock",
            "service_repo_map": {"checkout-api": "acme/checkout-api"},
        },
        headers=admin_headers,
    )
    assert conn_resp.status_code == 201
    connector = conn_resp.json()
    assert connector["mode"] == "mock"
    assert connector["has_credential"] is False

    test_resp = client.post(
        f"/api/v1/github/connectors/{connector['id']}/test", headers=admin_headers
    )
    assert test_resp.status_code == 200
    assert test_resp.json()["ok"] is True
    assert test_resp.json()["mode"] == "mock"

    # Create incident and correlate GitHub evidence
    inc = client.post(
        "/api/v1/incidents",
        json={"title": "Checkout 500s", "service": "checkout-api", "severity": "critical"},
        headers=admin_headers,
    ).json()

    corr = client.post(
        f"/api/v1/incidents/{inc['id']}/correlate-github",
        json={"lookback_hours": 24},
        headers=admin_headers,
    )
    assert corr.status_code == 200
    body = corr.json()
    assert body["mode"] == "mock"
    assert body["repository"] == "acme/checkout-api"
    assert "hypothesis" in body["disclaimer"].lower()
    assert len(body["evidence_items"]) >= 3
    for item in body["evidence_items"]:
        assert item["uri"].startswith("https://github.com/acme/checkout-api")
        assert item["metadata_json"]["hypothesis"] is True
        assert item["metadata_json"]["mode"] == "mock"
        assert "[DEMO/MOCK]" in item["title"]

    # Tenant B cannot access Tenant A's connector or correlate Tenant A's incident
    b_headers = login_client(client, tenants.b_owner.email)
    assert client.get("/api/v1/github/connectors").json() == []
    assert (
        client.post(
            f"/api/v1/github/connectors/{connector['id']}/test", headers=b_headers
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/incidents/{inc['id']}/correlate-github", headers=b_headers
        ).status_code
        == 404
    )


def test_live_connector_redacts_secrets_from_responses(client: TestClient, tenants: SeededTenants):
    admin_headers = login_client(client, tenants.a_admin.email)
    secret_pat = "github_pat_super_secret_token_value"
    webhook_sec = "whsec_super_secret_value"
    resp = client.post(
        "/api/v1/github/connectors",
        json={
            "name": "Live PAT",
            "mode": "live",
            "auth_type": "pat",
            "credential": secret_pat,
            "webhook_secret": webhook_sec,
            "service_repo_map": {"api": "acme/api"},
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201
    assert secret_pat not in resp.text
    assert webhook_sec not in resp.text
    assert resp.json()["has_credential"] is True
    assert resp.json()["has_webhook_secret"] is True


def test_github_client_http_mocks_etag_pagination_permissions_and_rate_limits():
    etag_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal etag_calls
        if request.url.path == "/app/installations/99/access_tokens":
            return httpx.Response(
                201,
                json={"token": "ghs_install_tok", "permissions": {"contents": "read"}},
            )
        if request.url.path == "/rate_limit":
            return httpx.Response(
                200,
                json={"resources": {"core": {"remaining": 4999}}},
                headers={"X-OAuth-Scopes": "repo:status"},
            )
        if request.url.path == "/repos/acme/api/commits":
            etag_calls += 1
            if request.headers.get("If-None-Match") == '"etag-1"':
                return httpx.Response(304)
            return httpx.Response(
                200,
                json=[
                    {
                        "sha": "1234567890abcdef",
                        "html_url": "https://github.com/acme/api/commit/1234567890abcdef",
                        "commit": {
                            "message": "fix: pool size",
                            "author": {"name": "Alice", "date": "2026-11-21T08:00:00Z"},
                        },
                    }
                ],
                headers={
                    "ETag": '"etag-1"',
                    "Link": '<https://api.github.com/repos/acme/api/commits?page=2>; rel="next"',
                },
            )
        if request.url.path == "/repos/acme/forbidden/commits":
            return httpx.Response(403, json={"message": "Resource not accessible"})
        if request.url.path == "/repos/acme/limited/commits":
            return httpx.Response(
                429, headers={"X-RateLimit-Remaining": "0"}, json={"message": "Rate limit"}
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    app_client = GitHubClient(
        auth_type=ScmAuthType.GITHUB_APP,
        credential=_test_rsa_pem(),
        app_id="12345",
        installation_id="99",
        transport=transport,
    )
    check = app_client.test_connection()
    assert check.ok is True
    assert check.permission_summary == {"contents": "read"}

    now = datetime.now(UTC)
    page1 = app_client.list_commits(
        "acme", "api", since=now - timedelta(hours=1), until=now, page=1, per_page=10
    )
    assert page1.has_next is True
    assert page1.items[0].sha == "1234567890abcdef"

    # Second call hits 304 ETag cache
    page1_cached = app_client.list_commits(
        "acme", "api", since=now - timedelta(hours=1), until=now, page=1, per_page=10
    )
    assert len(page1_cached.items) == 1
    assert etag_calls == 2

    with pytest.raises(ScmPermissionError):
        app_client.list_commits("acme", "forbidden", since=now - timedelta(hours=1), until=now)

    with pytest.raises(ScmRateLimitError):
        app_client.list_commits("acme", "limited", since=now - timedelta(hours=1), until=now)


def test_github_webhook_signature_malformed_and_deduplication(
    client: TestClient, tenants: SeededTenants
):
    admin_headers = login_client(client, tenants.a_admin.email)
    webhook_secret = "gh-webhook-secret-123"
    connector = client.post(
        "/api/v1/github/connectors",
        json={
            "name": "Webhook Receiver",
            "mode": "mock",
            "webhook_secret": webhook_secret,
        },
        headers=admin_headers,
    ).json()

    payload = {"action": "created", "repository": {"full_name": "acme/checkout-api"}}
    body = json.dumps(payload).encode("utf-8")
    sig = "sha256=" + hmac.new(webhook_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    # Bad signature -> 401
    assert (
        client.post(
            connector["webhook_path"],
            content=body,
            headers={
                "Content-Type": "application/json",
                GITHUB_SIGNATURE_HEADER: "sha256=bad",
                "X-GitHub-Delivery": "deliv-1",
                "X-GitHub-Event": "deployment",
            },
        ).status_code
        == 401
    )

    # Malformed JSON -> 422
    bad_json = b"{not-json"
    bad_sig = (
        "sha256=" + hmac.new(webhook_secret.encode("utf-8"), bad_json, hashlib.sha256).hexdigest()
    )
    assert (
        client.post(
            connector["webhook_path"],
            content=bad_json,
            headers={
                "Content-Type": "application/json",
                GITHUB_SIGNATURE_HEADER: bad_sig,
                "X-GitHub-Delivery": "deliv-bad",
                "X-GitHub-Event": "deployment",
            },
        ).status_code
        == 422
    )

    # Valid delivery -> recorded, duplicate delivery -> duplicate=True
    r1 = client.post(
        connector["webhook_path"],
        content=body,
        headers={
            "Content-Type": "application/json",
            GITHUB_SIGNATURE_HEADER: sig,
            "X-GitHub-Delivery": "deliv-1",
            "X-GitHub-Event": "deployment",
        },
    )
    assert r1.status_code == 202
    assert r1.json()["duplicate"] is False

    r2 = client.post(
        connector["webhook_path"],
        content=body,
        headers={
            "Content-Type": "application/json",
            GITHUB_SIGNATURE_HEADER: sig,
            "X-GitHub-Delivery": "deliv-1",
            "X-GitHub-Event": "deployment",
        },
    )
    assert r2.status_code == 202
    assert r2.json()["duplicate"] is True
