"""Core incident-management domain: lifecycle, concurrency, timeline, comments, evidence, search."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from tests.conftest import SeededTenants, login_client


def test_incident_lifecycle_state_machine_and_invalid_transitions(
    client: TestClient, tenants: SeededTenants
):
    headers = login_client(client, tenants.a_engineer.email)
    created = client.post(
        "/api/v1/incidents",
        json={
            "title": "Database connection pool exhausted",
            "service": "orders-api",
            "environment": "production",
            "severity": "critical",
            "affected_services": ["checkout-api", "orders-api"],
            "tags": ["Postgres", "Pool"],
        },
        headers=headers,
    ).json()
    inc_id = created["id"]
    assert created["status"] == "open"
    assert created["version"] == 1
    assert created["affected_services"] == ["checkout-api", "orders-api"]
    assert created["tags"] == ["pool", "postgres"]

    # OPEN -> ACKNOWLEDGED
    ack = client.post(
        f"/api/v1/incidents/{inc_id}/acknowledge",
        json={"note": "On-call investigating", "version": 1},
        headers=headers,
    )
    assert ack.status_code == 200
    assert ack.json()["status"] == "acknowledged"
    assert ack.json()["acknowledged_at"] is not None
    assert ack.json()["version"] == 2

    # ACKNOWLEDGED -> RESOLVED -> CLOSED
    res = client.post(f"/api/v1/incidents/{inc_id}/resolve", json={"version": 2}, headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "resolved"
    assert res.json()["resolved_at"] is not None

    closed = client.patch(
        f"/api/v1/incidents/{inc_id}/status",
        json={"status": "closed", "version": 3},
        headers=headers,
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    assert closed.json()["closed_at"] is not None

    # Invalid transition: CLOSED -> RESOLVED must fail with 409
    bad = client.post(f"/api/v1/incidents/{inc_id}/resolve", headers=headers)
    assert bad.status_code == 409
    assert bad.json()["error"] == "conflict"

    # CLOSED -> OPEN (reopen) clears resolved_at & closed_at
    reopened = client.post(f"/api/v1/incidents/{inc_id}/reopen", headers=headers)
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "open"
    assert reopened.json()["resolved_at"] is None
    assert reopened.json()["closed_at"] is None


def test_optimistic_concurrency_detects_stale_updates(client: TestClient, tenants: SeededTenants):
    headers = login_client(client, tenants.a_engineer.email)
    inc_id = client.post(
        "/api/v1/incidents",
        json={"title": "Concurrency check", "service": "api"},
        headers=headers,
    ).json()["id"]

    # First update at version 1 succeeds -> bumps to version 2.
    first = client.patch(
        f"/api/v1/incidents/{inc_id}",
        json={"title": "Concurrency check v2", "version": 1},
        headers=headers,
    )
    assert first.status_code == 200
    assert first.json()["version"] == 2

    # Stale update claiming version 1 (body or If-Match) must fail with 409.
    stale = client.patch(
        f"/api/v1/incidents/{inc_id}",
        json={"title": "Lost update", "version": 1},
        headers=headers,
    )
    assert stale.status_code == 409
    stale_header = client.post(
        f"/api/v1/incidents/{inc_id}/acknowledge",
        headers={**headers, "If-Match": '"1"'},
    )
    assert stale_header.status_code == 409


def test_assign_incident_enforces_same_organization_membership(
    client: TestClient, tenants: SeededTenants
):
    headers = login_client(client, tenants.a_engineer.email)
    inc_id = client.post(
        "/api/v1/incidents",
        json={"title": "Assign check", "service": "api"},
        headers=headers,
    ).json()["id"]

    # Assign to Tenant A admin -> succeeds.
    ok = client.post(
        f"/api/v1/incidents/{inc_id}/assign",
        json={"assignee_user_id": tenants.a_admin.id},
        headers=headers,
    )
    assert ok.status_code == 200
    assert ok.json()["assignee_user_id"] == tenants.a_admin.id

    # Assign to Tenant B owner -> 404 (cannot leak or assign across tenants).
    cross = client.post(
        f"/api/v1/incidents/{inc_id}/assign",
        json={"assignee_user_id": tenants.b_owner.id},
        headers=headers,
    )
    assert cross.status_code == 404


def test_timeline_comments_and_evidence_recorded_and_tenant_scoped(
    client: TestClient, tenants: SeededTenants
):
    a_headers = login_client(client, tenants.a_engineer.email)
    inc_id = client.post(
        "/api/v1/incidents",
        json={
            "title": "Latency spike",
            "service": "gateway",
            "metadata": {"password": "must-be-redacted", "region": "us-east-1"},
        },
        headers=a_headers,
    ).json()["id"]

    # Metadata secret is redacted.
    fetched = client.get(f"/api/v1/incidents/{inc_id}").json()
    assert fetched["metadata"]["password"] == "***"
    assert fetched["metadata"]["region"] == "us-east-1"

    comment = client.post(
        f"/api/v1/incidents/{inc_id}/comments",
        json={"body": "Checked upstream p99 latency."},
        headers=a_headers,
    )
    assert comment.status_code == 201

    evidence = client.post(
        f"/api/v1/incidents/{inc_id}/evidence",
        json={
            "kind": "metric",
            "title": "Gateway p99 > 2s",
            "uri": "https://metrics.internal/d/gw",
            "summary": "Spike started at 08:00 UTC.",
        },
        headers=a_headers,
    )
    assert evidence.status_code == 201

    timeline = client.get(f"/api/v1/incidents/{inc_id}/timeline").json()
    assert [e["event_type"] for e in timeline] == [
        "incident.created",
        "incident.comment_added",
        "incident.evidence_added",
    ]
    assert len(client.get(f"/api/v1/incidents/{inc_id}/comments").json()) == 1
    assert len(client.get(f"/api/v1/incidents/{inc_id}/evidence").json()) == 1

    # Tenant B cannot read or add timeline/comments/evidence on Tenant A's incident.
    b_headers = login_client(client, tenants.b_owner.email)
    assert client.get(f"/api/v1/incidents/{inc_id}/timeline").status_code == 404
    assert client.get(f"/api/v1/incidents/{inc_id}/comments").status_code == 404
    assert client.get(f"/api/v1/incidents/{inc_id}/evidence").status_code == 404
    assert (
        client.post(
            f"/api/v1/incidents/{inc_id}/comments", json={"body": "Snooped"}, headers=b_headers
        ).status_code
        == 404
    )


def test_filter_search_sort_and_pagination(client: TestClient, tenants: SeededTenants):
    headers = login_client(client, tenants.a_engineer.email)
    client.post(
        "/api/v1/incidents",
        json={
            "title": "Alpha low memory warning",
            "service": "worker",
            "environment": "staging",
            "severity": "low",
            "tags": ["memory"],
        },
        headers=headers,
    )
    inc2 = client.post(
        "/api/v1/incidents",
        json={
            "title": "Beta checkout outage",
            "service": "checkout-api",
            "environment": "production",
            "severity": "critical",
            "tags": ["outage", "payments"],
        },
        headers=headers,
    ).json()
    client.post(f"/api/v1/incidents/{inc2['id']}/acknowledge", headers=headers)
    client.post(
        "/api/v1/incidents",
        json={
            "title": "Gamma API timeout",
            "service": "checkout-api",
            "environment": "production",
            "severity": "high",
            "tags": ["latency"],
        },
        headers=headers,
    )

    # Filter by status + environment + tag
    assert len(client.get("/api/v1/incidents", params={"status": "acknowledged"}).json()) == 1
    assert len(client.get("/api/v1/incidents", params={"environment": "production"}).json()) == 2
    assert len(client.get("/api/v1/incidents", params={"tag": "PAYMENTS"}).json()) == 1

    # Search q
    q_resp = client.get("/api/v1/incidents", params={"q": "outage"})
    assert len(q_resp.json()) == 1
    assert q_resp.json()[0]["title"] == "Beta checkout outage"

    # Sort by severity desc -> critical, high, low
    sorted_resp = client.get(
        "/api/v1/incidents", params={"sort_by": "severity", "sort_order": "desc"}
    )
    assert [i["severity"] for i in sorted_resp.json()] == ["critical", "high", "low"]

    # Pagination + X-Total-Count
    page = client.get(
        "/api/v1/incidents",
        params={"sort_by": "severity", "sort_order": "desc", "limit": 2, "offset": 1},
    )
    assert page.headers["X-Total-Count"] == "3"
    assert [i["severity"] for i in page.json()] == ["high", "low"]

    # Time window filter
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    assert client.get("/api/v1/incidents", params={"created_after": future}).json() == []
