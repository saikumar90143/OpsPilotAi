"""Cross-tenant isolation and anti-IDOR checks."""

from fastapi.testclient import TestClient

from tests.conftest import SeededTenants, login_client


def test_tenant_b_cannot_read_update_archive_or_infer_tenant_a_incidents(
    client: TestClient, tenants: SeededTenants
):
    a_headers = login_client(client, tenants.a_owner.email)
    created = client.post(
        "/api/v1/incidents",
        json={
            "title": "Tenant A secret incident",
            "service": "billing-api",
            "severity": "critical",
        },
        headers=a_headers,
    )
    assert created.status_code == 201
    a_incident_id = created.json()["id"]

    # Switch session to Tenant B owner.
    b_headers = login_client(client, tenants.b_owner.email)
    assert client.get("/api/v1/incidents").json() == []
    # Must return 404 (not 403) so Tenant B cannot infer existence of Tenant A's ID.
    assert client.get(f"/api/v1/incidents/{a_incident_id}").status_code == 404
    assert (
        client.patch(
            f"/api/v1/incidents/{a_incident_id}/status",
            json={"status": "closed"},
            headers=b_headers,
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/incidents/{a_incident_id}", headers=b_headers).status_code == 404

    # Tenant A's incident is untouched.
    login_client(client, tenants.a_owner.email)
    assert client.get(f"/api/v1/incidents/{a_incident_id}").json()["status"] == "open"


def test_forged_organization_id_in_payload_cannot_bypass_isolation(
    client: TestClient, tenants: SeededTenants
):
    b_headers = login_client(client, tenants.b_owner.email)
    resp = client.post(
        "/api/v1/incidents",
        json={
            "title": "Forged org attempt",
            "service": "api",
            "organization_id": tenants.org_a.id,
        },
        headers=b_headers,
    )
    assert resp.status_code == 422

    # Verify Tenant A sees zero incidents.
    login_client(client, tenants.a_owner.email)
    assert client.get("/api/v1/incidents").json() == []


def test_tenant_b_cannot_access_tenant_a_memberships_invitations_or_audit_logs(
    client: TestClient, tenants: SeededTenants
):
    a_headers = login_client(client, tenants.a_owner.email)
    a_members = client.get("/api/v1/memberships").json()
    a_eng_membership_id = next(m["id"] for m in a_members if m["email"] == tenants.a_engineer.email)
    a_invite_id = client.post(
        "/api/v1/invitations",
        json={"email": "invitee@acme.local", "role": "viewer"},
        headers=a_headers,
    ).json()["id"]

    b_headers = login_client(client, tenants.b_owner.email)
    b_members = client.get("/api/v1/memberships").json()
    assert [m["email"] for m in b_members] == [tenants.b_owner.email]
    assert client.get("/api/v1/invitations").json() == []

    # Cross-tenant membership & invitation mutations return 404.
    assert (
        client.patch(
            f"/api/v1/memberships/{a_eng_membership_id}/role",
            json={"role": "viewer"},
            headers=b_headers,
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/memberships/{a_eng_membership_id}", headers=b_headers).status_code
        == 404
    )
    assert client.delete(f"/api/v1/invitations/{a_invite_id}", headers=b_headers).status_code == 404

    # Tenant B's audit logs do not include Tenant A events.
    b_audit = client.get("/api/v1/audit-logs").json()
    assert all(entry["organization_id"] == tenants.org_b.id for entry in b_audit)
