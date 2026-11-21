"""Server-side RBAC enforcement for OWNER, ADMIN, ENGINEER, and VIEWER."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.permissions import Role
from app.models.membership import Membership
from tests.conftest import SeededTenants, login_client


def test_viewer_is_read_only(client: TestClient, tenants: SeededTenants):
    headers = login_client(client, tenants.a_viewer.email)

    assert client.get("/api/v1/incidents").status_code == 200
    assert client.get("/api/v1/organizations/current").status_code == 200
    assert client.get("/api/v1/memberships").status_code == 200

    assert (
        client.post(
            "/api/v1/incidents", json={"title": "Viewer create", "service": "api"}, headers=headers
        ).status_code
        == 403
    )
    assert (
        client.patch(
            "/api/v1/organizations/current", json={"name": "Hijacked"}, headers=headers
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/invitations",
            json={"email": "x@acme.local", "role": "viewer"},
            headers=headers,
        ).status_code
        == 403
    )
    assert client.get("/api/v1/invitations").status_code == 403
    assert client.get("/api/v1/audit-logs").status_code == 403


def test_engineer_can_write_incidents_but_cannot_archive_or_admin(
    client: TestClient, tenants: SeededTenants
):
    headers = login_client(client, tenants.a_engineer.email)
    created = client.post(
        "/api/v1/incidents", json={"title": "Eng incident", "service": "api"}, headers=headers
    )
    assert created.status_code == 201
    inc_id = created.json()["id"]

    assert (
        client.patch(
            f"/api/v1/incidents/{inc_id}/status",
            json={"status": "investigating"},
            headers=headers,
        ).status_code
        == 200
    )
    assert client.delete(f"/api/v1/incidents/{inc_id}", headers=headers).status_code == 403
    assert (
        client.post(
            "/api/v1/invitations",
            json={"email": "x@acme.local", "role": "viewer"},
            headers=headers,
        ).status_code
        == 403
    )
    assert client.get("/api/v1/audit-logs").status_code == 403


def test_admin_can_archive_invite_and_read_audit_but_cannot_update_org_or_promote_admin(
    client: TestClient, tenants: SeededTenants, session_factory: sessionmaker[Session]
):
    headers = login_client(client, tenants.a_admin.email)
    inc_id = client.post(
        "/api/v1/incidents", json={"title": "Admin archive", "service": "api"}, headers=headers
    ).json()["id"]

    assert client.delete(f"/api/v1/incidents/{inc_id}", headers=headers).status_code == 204
    assert client.get("/api/v1/audit-logs").status_code == 200
    assert (
        client.patch(
            "/api/v1/organizations/current", json={"name": "Admin rename"}, headers=headers
        ).status_code
        == 403
    )

    members = client.get("/api/v1/memberships").json()
    eng_member_id = next(m["id"] for m in members if m["email"] == tenants.a_engineer.email)
    owner_member_id = next(m["id"] for m in members if m["email"] == tenants.a_owner.email)

    # Admin can demote engineer -> viewer, but cannot promote engineer -> admin or touch owner.
    assert (
        client.patch(
            f"/api/v1/memberships/{eng_member_id}/role",
            json={"role": "viewer"},
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/memberships/{eng_member_id}/role",
            json={"role": "admin"},
            headers=headers,
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/v1/memberships/{owner_member_id}/role",
            json={"role": "viewer"},
            headers=headers,
        ).status_code
        == 403
    )


def test_owner_can_update_org_and_manage_admin_roles(client: TestClient, tenants: SeededTenants):
    headers = login_client(client, tenants.a_owner.email)
    rename = client.patch(
        "/api/v1/organizations/current", json={"name": "Acme Ops Global"}, headers=headers
    )
    assert rename.status_code == 200
    assert rename.json()["name"] == "Acme Ops Global"

    members = client.get("/api/v1/memberships").json()
    eng_id = next(m["id"] for m in members if m["email"] == tenants.a_engineer.email)
    promote = client.patch(
        f"/api/v1/memberships/{eng_id}/role", json={"role": "admin"}, headers=headers
    )
    assert promote.status_code == 200
    assert promote.json()["role"] == "admin"


def test_demotion_takes_effect_immediately_against_existing_token(
    client: TestClient, tenants: SeededTenants, session_factory: sessionmaker[Session]
):
    eng_headers = login_client(client, tenants.a_engineer.email)
    assert (
        client.post(
            "/api/v1/incidents",
            json={"title": "Before demotion", "service": "api"},
            headers=eng_headers,
        ).status_code
        == 201
    )

    # Demote engineer to viewer in DB while the old access token is still valid.
    with session_factory() as db:
        membership = (
            db.query(Membership)
            .filter(
                Membership.organization_id == tenants.org_a.id,
                Membership.user_id == tenants.a_engineer.id,
            )
            .one()
        )
        membership.role = Role.VIEWER.value
        db.commit()

    assert (
        client.post(
            "/api/v1/incidents",
            json={"title": "After demotion", "service": "api"},
            headers=eng_headers,
        ).status_code
        == 403
    )
