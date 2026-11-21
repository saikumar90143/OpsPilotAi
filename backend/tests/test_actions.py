"""Phase 9 tests: controlled external write actions, human approval gate, idempotency, RBAC."""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient

from app.core.permissions import Role
from app.integrations.actions.base import (
    ActionConnectionTestResult,
    ActionExecutionResult,
    ActionPermissionError,
    ActionTimeoutError,
)
from app.models.action import ProposedAction, ProposedActionStatus
from app.models.membership import Membership
from app.services import action_service
from tests.conftest import TEST_PASSWORD, login_client


def _create_incident(client: TestClient, headers: dict[str, str]) -> int:
    resp = client.post(
        "/api/v1/incidents",
        headers=headers,
        json={
            "title": "Checkout DB pool exhaustion",
            "description": "High 500 rate",
            "service": "checkout-api",
            "environment": "production",
            "severity": "high",
        },
    )
    assert resp.status_code == 201
    return int(resp.json()["id"])


def test_connector_allowlist_approval_gate_separation_of_duties_and_idempotency(
    client: TestClient, tenants
):
    admin_headers = login_client(client, "admin@acme.local", TEST_PASSWORD)

    jira_conn = client.post(
        "/api/v1/action-connectors",
        headers=admin_headers,
        json={
            "provider": "jira",
            "name": "Acme Jira (Mock)",
            "mode": "mock",
            "allowed_targets": ["OPS", "ENG"],
        },
    )
    assert jira_conn.status_code == 201
    jira_id = jira_conn.json()["id"]
    assert jira_conn.json()["mode"] == "mock"
    assert "encrypted_credential" not in jira_conn.json()

    test_res = client.post(f"/api/v1/action-connectors/{jira_id}/test", headers=admin_headers)
    assert test_res.status_code == 200
    assert test_res.json()["ok"] is True
    assert test_res.json()["mode"] == "mock"

    slack_conn = client.post(
        "/api/v1/action-connectors",
        headers=admin_headers,
        json={
            "provider": "slack",
            "name": "Acme Slack (Mock)",
            "mode": "mock",
            "allowed_targets": ["C01OPS"],
        },
    )
    assert slack_conn.status_code == 201
    slack_id = slack_conn.json()["id"]

    # Engineer proposes Jira issue
    eng_headers = login_client(client, "eng@acme.local", TEST_PASSWORD)
    inc_id = _create_incident(client, eng_headers)

    # Disallowed target project rejected
    bad_target = client.post(
        f"/api/v1/incidents/{inc_id}/actions",
        headers=eng_headers,
        json={
            "connector_id": jira_id,
            "action_type": "jira_create_issue",
            "target_destination": "FINANCE",
            "payload": {"summary": "Incident issue", "description": "Details here"},
        },
    )
    assert bad_target.status_code == 422

    # Valid Jira proposal
    prop_resp = client.post(
        f"/api/v1/incidents/{inc_id}/actions",
        headers=eng_headers,
        json={
            "connector_id": jira_id,
            "action_type": "jira_create_issue",
            "target_destination": "OPS",
            "payload": {
                "summary": "Checkout DB pool exhausted",
                "description": "See EV-LOG-1 and EV-KB-1",
            },
            "evidence_links": ["EV-LOG-1", "EV-KB-1"],
            "idempotency_key": "jira-inc-1",
        },
    )
    assert prop_resp.status_code == 201
    action = prop_resp.json()
    action_id = action["id"]
    assert action["status"] == "proposed"
    assert action["connector_mode"] == "mock"

    # Unapproved action cannot execute (409)
    assert (
        client.post(f"/api/v1/actions/{action_id}/execute", headers=eng_headers).status_code == 409
    )

    # Separation of duties: proposer cannot self-approve (403)
    assert (
        client.post(f"/api/v1/actions/{action_id}/approve", headers=eng_headers).status_code == 403
    )

    # Admin approves and executes
    admin_headers = login_client(client, "admin@acme.local", TEST_PASSWORD)
    app_resp = client.post(f"/api/v1/actions/{action_id}/approve", headers=admin_headers)
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == "approved"

    exec1 = client.post(f"/api/v1/actions/{action_id}/execute", headers=admin_headers)
    assert exec1.status_code == 200
    assert exec1.json()["status"] == "succeeded"
    ext_id = exec1.json()["external_id"]
    assert ext_id.startswith("MOCK-OPS-")

    # Duplicate execution is idempotent
    exec2 = client.post(f"/api/v1/actions/{action_id}/execute", headers=admin_headers)
    assert exec2.status_code == 200
    assert exec2.json()["external_id"] == ext_id
    assert exec2.json()["execution_attempts"] == exec1.json()["execution_attempts"]

    # Slack proposal & reject flow
    slack_prop = client.post(
        f"/api/v1/incidents/{inc_id}/actions",
        headers=admin_headers,
        json={
            "connector_id": slack_id,
            "action_type": "slack_post_message",
            "target_destination": "C01OPS",
            "payload": {"text": "Investigating checkout-api DB pool exhaustion."},
        },
    )
    assert slack_prop.status_code == 201
    slack_action_id = slack_prop.json()["id"]

    rej_resp = client.post(
        f"/api/v1/actions/{slack_action_id}/reject",
        headers=admin_headers,
        json={"reason": "Duplicate notification"},
    )
    assert rej_resp.status_code == 200
    assert rej_resp.json()["status"] == "rejected"
    assert (
        client.post(f"/api/v1/actions/{slack_action_id}/execute", headers=admin_headers).status_code
        == 409
    )

    # Audit trail recorded
    audits = client.get("/api/v1/audit-logs?limit=50").json()
    audit_actions = {a["action"] for a in audits}
    assert "proposed_action.created" in audit_actions
    assert "proposed_action.approved" in audit_actions
    assert "proposed_action.executed" in audit_actions
    assert "proposed_action.rejected" in audit_actions


def test_rbac_execution_reverification_and_tenant_isolation(
    client: TestClient, session_factory, tenants
):
    admin_headers = login_client(client, "admin@acme.local", TEST_PASSWORD)
    conn_id = client.post(
        "/api/v1/action-connectors",
        headers=admin_headers,
        json={
            "provider": "slack",
            "name": "Slack",
            "mode": "mock",
            "allowed_targets": ["C01OPS"],
        },
    ).json()["id"]
    inc_id = _create_incident(client, admin_headers)
    action_id = client.post(
        f"/api/v1/incidents/{inc_id}/actions",
        headers=admin_headers,
        json={
            "connector_id": conn_id,
            "action_type": "slack_post_message",
            "target_destination": "C01OPS",
            "payload": {"text": "Alerting #ops"},
        },
    ).json()["id"]

    # Viewer denied
    viewer_headers = login_client(client, "viewer@acme.local", TEST_PASSWORD)
    assert (
        client.post(f"/api/v1/actions/{action_id}/approve", headers=viewer_headers).status_code
        == 403
    )

    # Engineer approves
    eng_headers = login_client(client, "eng@acme.local", TEST_PASSWORD)
    assert (
        client.post(f"/api/v1/actions/{action_id}/approve", headers=eng_headers).status_code == 200
    )

    # Demote engineer to viewer in DB before execution -> execution re-check must deny (403)
    with session_factory() as db:
        mem = db.query(Membership).filter(Membership.user_id == tenants.a_engineer.id).one()
        mem.role = Role.VIEWER.value
        db.commit()

    assert (
        client.post(f"/api/v1/actions/{action_id}/execute", headers=eng_headers).status_code == 403
    )

    # Cross-tenant Beta owner denied (404)
    beta_headers = login_client(client, "owner@beta.local", TEST_PASSWORD)
    assert (
        client.post(f"/api/v1/actions/{action_id}/execute", headers=beta_headers).status_code == 404
    )
    assert client.get("/api/v1/actions").json() == []


def test_modified_payload_expired_approval_timeout_retry_and_permission_denied(
    client: TestClient, session_factory, tenants
):
    admin_headers = login_client(client, "admin@acme.local", TEST_PASSWORD)
    conn_id = client.post(
        "/api/v1/action-connectors",
        headers=admin_headers,
        json={
            "provider": "jira",
            "name": "Jira",
            "mode": "mock",
            "allowed_targets": ["OPS"],
        },
    ).json()["id"]
    inc_id = _create_incident(client, admin_headers)

    # 1. Modified payload after approval invalidated
    a1_id = client.post(
        f"/api/v1/incidents/{inc_id}/actions",
        headers=admin_headers,
        json={
            "connector_id": conn_id,
            "action_type": "jira_create_issue",
            "target_destination": "OPS",
            "payload": {"summary": "Original summary", "description": "Original desc"},
            "requested_by_type": "ai",
        },
    ).json()["id"]
    assert client.post(f"/api/v1/actions/{a1_id}/approve", headers=admin_headers).status_code == 200
    with session_factory() as db:
        row = db.get(ProposedAction, a1_id)
        assert row is not None
        row.payload_preview_json = {"summary": "Tampered summary", "description": "Original desc"}
        db.commit()
    tampered = client.post(f"/api/v1/actions/{a1_id}/execute", headers=admin_headers)
    assert tampered.status_code == 409

    # 2. Expired approval rejected
    a2_id = client.post(
        f"/api/v1/incidents/{inc_id}/actions",
        headers=admin_headers,
        json={
            "connector_id": conn_id,
            "action_type": "jira_create_issue",
            "target_destination": "OPS",
            "payload": {"summary": "Expiring action", "description": "Details"},
            "requested_by_type": "ai",
        },
    ).json()["id"]
    with session_factory() as db:
        row2 = db.get(ProposedAction, a2_id)
        assert row2 is not None
        row2.expires_at = datetime.now(UTC) - timedelta(minutes=5)
        db.commit()
    exp_resp = client.post(f"/api/v1/actions/{a2_id}/approve", headers=admin_headers)
    assert exp_resp.status_code == 409

    # 3. Transient timeout retries safely without duplicate tickets; permission denied fails cleanly
    a3_id = client.post(
        f"/api/v1/incidents/{inc_id}/actions",
        headers=admin_headers,
        json={
            "connector_id": conn_id,
            "action_type": "jira_create_issue",
            "target_destination": "OPS",
            "payload": {"summary": "Retryable action", "description": "Details"},
            "requested_by_type": "ai",
        },
    ).json()["id"]
    assert client.post(f"/api/v1/actions/{a3_id}/approve", headers=admin_headers).status_code == 200

    class FlakyThenOkProvider:
        def __init__(self) -> None:
            self.calls = 0

        def test_connection(self) -> ActionConnectionTestResult:
            return ActionConnectionTestResult(True, "mock", {}, "ok")

        def execute_action(
            self,
            *,
            action_type: str,
            destination: str,
            payload: dict[str, Any],
            idempotency_key: str,
        ) -> ActionExecutionResult:
            self.calls += 1
            if self.calls == 1:
                raise ActionTimeoutError("Transient timeout")
            return ActionExecutionResult("MOCK-OPS-777", None, {"ok": True}, True)

    class DeniedProvider:
        def test_connection(self) -> ActionConnectionTestResult:
            return ActionConnectionTestResult(False, "mock", {}, "denied")

        def execute_action(self, **kwargs: Any) -> ActionExecutionResult:
            raise ActionPermissionError("403 Forbidden: Bearer secret-should-be-redacted")

    with session_factory() as db:
        flaky = FlakyThenOkProvider()
        res_ok, _ = action_service.execute_action(
            db,
            organization_id=tenants.org_a.id,
            actor_user_id=tenants.a_admin.id,
            action_id=a3_id,
            provider_override=flaky,
        )
        assert res_ok.status == ProposedActionStatus.SUCCEEDED.value
        assert res_ok.external_id == "MOCK-OPS-777"
        assert res_ok.execution_attempts == 2

        a4_id = client.post(
            f"/api/v1/incidents/{inc_id}/actions",
            headers=admin_headers,
            json={
                "connector_id": conn_id,
                "action_type": "jira_create_issue",
                "target_destination": "OPS",
                "payload": {"summary": "Denied action", "description": "Details"},
                "requested_by_type": "ai",
            },
        ).json()["id"]
        assert (
            client.post(f"/api/v1/actions/{a4_id}/approve", headers=admin_headers).status_code
            == 200
        )
        res_denied, _ = action_service.execute_action(
            db,
            organization_id=tenants.org_a.id,
            actor_user_id=tenants.a_admin.id,
            action_id=a4_id,
            provider_override=DeniedProvider(),
        )
        assert res_denied.status == ProposedActionStatus.FAILED.value
        assert "secret-should-be-redacted" not in (res_denied.last_error or "")
        assert "[REDACTED_SECRET]" in (res_denied.last_error or "")
