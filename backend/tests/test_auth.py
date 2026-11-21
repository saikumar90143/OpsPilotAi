"""Authentication lifecycle: Argon2id, cookies, CSRF, refresh rotation, reuse, rate limits."""

from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import ACCESS_COOKIE_NAME, CSRF_COOKIE_NAME, CSRF_HEADER_NAME, REFRESH_COOKIE_NAME
from app.core.config import get_settings
from app.core.permissions import Role
from app.core.security import verify_password
from app.models.refresh_token import RefreshToken
from tests.conftest import TEST_PASSWORD, SeededTenants, login_client


def test_unauthenticated_requests_rejected(client: TestClient):
    for method, path in (
        ("GET", "/api/v1/auth/me"),
        ("GET", "/api/v1/organizations/current"),
        ("GET", "/api/v1/memberships"),
        ("GET", "/api/v1/invitations"),
        ("GET", "/api/v1/audit-logs"),
        ("GET", "/api/v1/incidents"),
        ("POST", "/api/v1/incidents"),
    ):
        resp = client.request(method, path)
        assert resp.status_code == 401, f"{method} {path} returned {resp.status_code}"


def test_passwords_hashed_with_argon2id_and_never_returned(
    client: TestClient, tenants: SeededTenants
):
    assert tenants.a_owner.password_hash.startswith("$argon2id$")
    assert verify_password(TEST_PASSWORD, tenants.a_owner.password_hash)

    headers = login_client(client, tenants.a_owner.email)
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert "password" not in me_resp.text
    assert "password_hash" not in me_resp.text
    assert tenants.a_owner.password_hash not in me_resp.text

    members_resp = client.get("/api/v1/memberships")
    assert members_resp.status_code == 200
    assert "password_hash" not in members_resp.text


def test_login_sets_httponly_cookies_and_generic_error_on_failure(
    client: TestClient, tenants: SeededTenants
):
    # Unknown email and wrong password must produce the exact same generic failure.
    unknown_resp = client.post(
        "/api/v1/auth/login", json={"email": "nobody@acme.local", "password": TEST_PASSWORD}
    )
    wrong_pw_resp = client.post(
        "/api/v1/auth/login", json={"email": tenants.a_owner.email, "password": "wrong-password"}
    )
    assert unknown_resp.status_code == 401
    assert wrong_pw_resp.status_code == 401
    assert unknown_resp.json()["message"] == wrong_pw_resp.json()["message"]
    assert unknown_resp.json()["message"] == "Invalid email or password"

    ok_resp = client.post(
        "/api/v1/auth/login", json={"email": tenants.a_owner.email, "password": TEST_PASSWORD}
    )
    assert ok_resp.status_code == 200
    set_cookies = ok_resp.headers.get_list("set-cookie")
    access_cookie = next(c for c in set_cookies if c.startswith(f"{ACCESS_COOKIE_NAME}="))
    refresh_cookie = next(c for c in set_cookies if c.startswith(f"{REFRESH_COOKIE_NAME}="))
    assert "httponly" in access_cookie.lower()
    assert "httponly" in refresh_cookie.lower()
    assert "samesite=lax" in access_cookie.lower()


def test_csrf_required_for_cookie_state_changing_requests(
    client: TestClient, tenants: SeededTenants
):
    headers = login_client(client, tenants.a_engineer.email)
    no_csrf = client.post("/api/v1/incidents", json={"title": "No CSRF", "service": "api"})
    assert no_csrf.status_code == 403

    bad_csrf = client.post(
        "/api/v1/incidents",
        json={"title": "Bad CSRF", "service": "api"},
        headers={CSRF_HEADER_NAME: "wrong-token"},
    )
    assert bad_csrf.status_code == 403

    ok = client.post(
        "/api/v1/incidents", json={"title": "Valid CSRF", "service": "api"}, headers=headers
    )
    assert ok.status_code == 201


def test_refresh_rotation_and_reuse_revokes_entire_family(
    client: TestClient, tenants: SeededTenants, session_factory: sessionmaker[Session]
):
    headers = login_client(client, tenants.a_owner.email)
    first_refresh = client.cookies.get(REFRESH_COOKIE_NAME)
    assert first_refresh

    rotated = client.post("/api/v1/auth/refresh", headers=headers)
    assert rotated.status_code == 200
    second_refresh = rotated.cookies.get(REFRESH_COOKIE_NAME)
    assert second_refresh and second_refresh != first_refresh

    # Replay the already-rotated first refresh token -> reuse detected -> whole family revoked.
    csrf_val = client.cookies.get(CSRF_COOKIE_NAME) or ""
    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE_NAME, first_refresh, path="/api/v1/auth")
    client.cookies.set(CSRF_COOKIE_NAME, csrf_val, path="/")
    reuse_resp = client.post("/api/v1/auth/refresh", headers={CSRF_HEADER_NAME: csrf_val})
    assert reuse_resp.status_code == 401

    with session_factory() as db:
        tokens = list(db.scalars(select(RefreshToken)).all())
        assert len(tokens) == 2
        assert all(t.revoked_at is not None for t in tokens)

    # Even the second token is now revoked because its family was killed.
    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE_NAME, second_refresh, path="/api/v1/auth")
    client.cookies.set(CSRF_COOKIE_NAME, csrf_val, path="/")
    after_kill = client.post("/api/v1/auth/refresh", headers={CSRF_HEADER_NAME: csrf_val})
    assert after_kill.status_code == 401


def test_logout_revokes_refresh_family_and_clears_cookies(
    client: TestClient, tenants: SeededTenants
):
    headers = login_client(client, tenants.a_owner.email)
    old_refresh = client.cookies.get(REFRESH_COOKIE_NAME)
    old_csrf = headers[CSRF_HEADER_NAME]
    logout_resp = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_resp.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401

    # Reusing the logged-out refresh token (even with matching CSRF) must fail.
    client.cookies.set(REFRESH_COOKIE_NAME, old_refresh or "", path="/api/v1/auth")
    client.cookies.set(CSRF_COOKIE_NAME, old_csrf, path="/")
    assert client.post("/api/v1/auth/refresh", headers=headers).status_code == 401


def test_expired_and_tampered_access_tokens_fail(client: TestClient, tenants: SeededTenants):
    settings = get_settings()
    expired = jwt.encode(
        {
            "sub": str(tenants.a_owner.id),
            "org": tenants.org_a.id,
            "role": Role.OWNER.value,
            "type": "access",
            "jti": "expired-jti",
            "iat": int((datetime.now(UTC) - timedelta(hours=2)).timestamp()),
            "exp": int((datetime.now(UTC) - timedelta(hours=1)).timestamp()),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code
        == 401
    )
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer tampered.jwt.token"}
        ).status_code
        == 401
    )


def test_auth_rate_limiting(client: TestClient, tenants: SeededTenants):
    limit = get_settings().auth_rate_limit_requests
    for _ in range(limit):
        resp = client.post(
            "/api/v1/auth/login", json={"email": tenants.a_owner.email, "password": "wrong"}
        )
        assert resp.status_code == 401
    blocked = client.post(
        "/api/v1/auth/login", json={"email": tenants.a_owner.email, "password": TEST_PASSWORD}
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"] == "rate_limited"


def test_invitation_accept_flow_and_no_public_owner_signup(
    client: TestClient, tenants: SeededTenants
):
    admin_headers = login_client(client, tenants.a_admin.email)
    invite_resp = client.post(
        "/api/v1/invitations",
        json={"email": "new.eng@acme.local", "role": "engineer"},
        headers=admin_headers,
    )
    assert invite_resp.status_code == 201
    raw_token = invite_resp.json()["invite_token"]

    # Cannot invite directly as owner.
    owner_invite = client.post(
        "/api/v1/invitations",
        json={"email": "bad@acme.local", "role": "owner"},
        headers=admin_headers,
    )
    assert owner_invite.status_code == 422

    # Accept invite -> authenticates as ENGINEER in Acme Ops.
    accept_resp = client.post(
        "/api/v1/auth/accept-invite",
        json={"token": raw_token, "full_name": "New Engineer", "password": "StrongPassword99!"},
    )
    assert accept_resp.status_code == 201
    assert accept_resp.json()["role"] == "engineer"
    assert accept_resp.json()["organization"]["id"] == tenants.org_a.id

    # Re-using the same invite token fails.
    reuse = client.post(
        "/api/v1/auth/accept-invite",
        json={"token": raw_token, "full_name": "Again", "password": "StrongPassword99!"},
    )
    assert reuse.status_code == 401
