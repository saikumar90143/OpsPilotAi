"""Event ingestion tests: Alertmanager adapter, HMAC+rotation, idempotency, retries, DLQ."""

import json
import time

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.webhooks import get_enqueue_fn
from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError
from app.core.secrets import SIGNATURE_HEADER, sign_webhook_payload
from app.integrations.alertmanager import build_sample_alertmanager_payload
from app.integrations.base import AlertEventStatus
from app.main import app
from app.models.inbound_event import InboundEvent, InboundEventStatus
from app.models.incident_details import IncidentTimelineEvent
from app.services import ingestion_service
from tests.conftest import SeededTenants, login_client


def _setup_live_integration(client: TestClient, headers: dict[str, str]) -> dict:
    resp = client.post(
        "/api/v1/integrations",
        json={"provider": "alertmanager", "name": "Prod Alertmanager", "is_simulator_mode": False},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()


def test_valid_alertmanager_webhook_idempotency_and_incident_mapping(
    client: TestClient, tenants: SeededTenants, session_factory: sessionmaker[Session]
):
    enqueued: list[int] = []
    app.dependency_overrides[get_enqueue_fn] = lambda: lambda ev_id, _cid: enqueued.append(ev_id)

    admin_headers = login_client(client, tenants.a_admin.email)
    integration = _setup_live_integration(client, admin_headers)
    assert integration["connection_status"] == "configured"
    assert "encrypted_signing_secret" not in integration

    # Secrets must not appear in subsequent GET /integrations
    listed = client.get("/api/v1/integrations").json()
    assert "signing_secret" not in listed[0]
    assert integration["signing_secret"] not in client.get("/api/v1/integrations").text

    payload = build_sample_alertmanager_payload(
        scenario="high_error_rate", status=AlertEventStatus.FIRING
    )
    raw_body = json.dumps(payload).encode("utf-8")
    sig = sign_webhook_payload(raw_body, integration["signing_secret"])

    # First delivery -> 202 queued, 1 event persisted
    resp1 = client.post(
        integration["webhook_path"],
        content=raw_body,
        headers={"Content-Type": "application/json", SIGNATURE_HEADER: sig},
    )
    assert resp1.status_code == 202
    assert resp1.json()["duplicate"] is False
    assert len(enqueued) == 1

    # Process via worker logic
    with session_factory() as db:
        outcome = ingestion_service.execute_event_processing(db, event_id=enqueued[0])
        assert outcome.status is InboundEventStatus.PROCESSED

    incidents = client.get("/api/v1/incidents").json()
    assert len(incidents) == 1
    inc_id = incidents[0]["id"]
    assert incidents[0]["source"] == "alertmanager"

    # Replaying exact same payload -> idempotent duplicate, no second job or timeline entry
    resp2 = client.post(
        integration["webhook_path"],
        content=raw_body,
        headers={"Content-Type": "application/json", SIGNATURE_HEADER: sig},
    )
    assert resp2.status_code == 202
    assert resp2.json()["duplicate"] is True
    assert len(enqueued) == 1

    with session_factory() as db:
        timeline = list(
            db.scalars(
                select(IncidentTimelineEvent).where(IncidentTimelineEvent.incident_id == inc_id)
            ).all()
        )
        assert len(timeline) == 1

    # Resolved Alertmanager webhook with same fingerprint resolves the existing incident
    resolved_payload = build_sample_alertmanager_payload(
        scenario="high_error_rate", status=AlertEventStatus.RESOLVED
    )
    resolved_body = json.dumps(resolved_payload).encode("utf-8")
    resolved_sig = sign_webhook_payload(resolved_body, integration["signing_secret"])
    res_resp = client.post(
        integration["webhook_path"],
        content=resolved_body,
        headers={"Content-Type": "application/json", SIGNATURE_HEADER: resolved_sig},
    )
    assert res_resp.status_code == 202
    with session_factory() as db:
        ingestion_service.execute_event_processing(db, event_id=enqueued[1])
    assert client.get(f"/api/v1/incidents/{inc_id}").json()["status"] == "resolved"


def test_signature_replay_protection_and_secret_rotation(
    client: TestClient, tenants: SeededTenants
):
    app.dependency_overrides[get_enqueue_fn] = lambda: lambda _ev_id, _cid: None
    admin_headers = login_client(client, tenants.a_admin.email)
    integration = _setup_live_integration(client, admin_headers)
    old_secret = integration["signing_secret"]

    body = json.dumps(build_sample_alertmanager_payload()).encode("utf-8")

    # Bad signature -> 401
    assert (
        client.post(
            integration["webhook_path"],
            content=body,
            headers={"Content-Type": "application/json", SIGNATURE_HEADER: "t=1,v1=deadbeef"},
        ).status_code
        == 401
    )

    # Stale timestamp outside replay window -> 401
    stale_ts = int(time.time()) - 600
    stale_sig = sign_webhook_payload(body, old_secret, timestamp=stale_ts)
    assert (
        client.post(
            integration["webhook_path"],
            content=body,
            headers={"Content-Type": "application/json", SIGNATURE_HEADER: stale_sig},
        ).status_code
        == 401
    )

    # Rotate secret -> old secret still accepted during grace window, new secret also works
    rotated = client.post(
        f"/api/v1/integrations/{integration['id']}/rotate-secret", headers=admin_headers
    ).json()
    new_secret = rotated["signing_secret"]
    assert new_secret != old_secret

    old_sig = sign_webhook_payload(body, old_secret)
    assert (
        client.post(
            integration["webhook_path"],
            content=body,
            headers={"Content-Type": "application/json", SIGNATURE_HEADER: old_sig},
        ).status_code
        == 202
    )

    # New secret with Bearer fallback (for providers that cannot sign bodies)
    payload2 = build_sample_alertmanager_payload(scenario="queue_backlog")
    body2 = json.dumps(payload2).encode("utf-8")
    assert (
        client.post(
            integration["webhook_path"],
            content=body2,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {new_secret}"},
        ).status_code
        == 202
    )


def test_invalid_payload_and_payload_size_limit(client: TestClient, tenants: SeededTenants):
    app.dependency_overrides[get_enqueue_fn] = lambda: lambda _ev_id, _cid: None
    admin_headers = login_client(client, tenants.a_admin.email)
    integration = _setup_live_integration(client, admin_headers)
    secret = integration["signing_secret"]

    # Invalid Alertmanager schema (missing alerts) -> 422
    bad_body = json.dumps({"groupKey": "g1", "status": "firing", "alerts": []}).encode("utf-8")
    assert (
        client.post(
            integration["webhook_path"],
            content=bad_body,
            headers={
                "Content-Type": "application/json",
                SIGNATURE_HEADER: sign_webhook_payload(bad_body, secret),
            },
        ).status_code
        == 422
    )

    # Oversized payload -> 413
    oversized = b"{" + b" " * (get_settings().webhook_max_bytes + 10) + b"}"
    assert (
        client.post(
            integration["webhook_path"],
            content=oversized,
            headers={
                "Content-Type": "application/json",
                SIGNATURE_HEADER: sign_webhook_payload(oversized, secret),
            },
        ).status_code
        == 413
    )


def test_queue_unavailable_persists_receipt_and_allows_admin_replay(
    client: TestClient, tenants: SeededTenants, session_factory: sessionmaker[Session]
):
    def failing_enqueue(_ev_id: int, _cid: str) -> None:
        raise ServiceUnavailableError("Redis down")

    app.dependency_overrides[get_enqueue_fn] = lambda: failing_enqueue
    admin_headers = login_client(client, tenants.a_admin.email)
    integration = _setup_live_integration(client, admin_headers)

    body = json.dumps(build_sample_alertmanager_payload()).encode("utf-8")
    sig = sign_webhook_payload(body, integration["signing_secret"])
    resp = client.post(
        integration["webhook_path"],
        content=body,
        headers={"Content-Type": "application/json", SIGNATURE_HEADER: sig},
    )
    assert resp.status_code == 503

    # Receipt is persisted and visible in /api/v1/events
    events = client.get("/api/v1/events").json()
    assert len(events) == 1
    assert events[0]["status"] == "received"
    assert events[0]["last_error"] == "Redis down"

    # Once queue recovers, admin replays it
    replayed_ids: list[int] = []
    app.dependency_overrides[get_enqueue_fn] = lambda: (
        lambda ev_id, _cid: replayed_ids.append(ev_id)
    )
    replay_resp = client.post(f"/api/v1/events/{events[0]['id']}/replay", headers=admin_headers)
    assert replay_resp.status_code == 200
    assert replay_resp.json()["status"] == "queued"
    assert replayed_ids == [events[0]["id"]]


def test_worker_retry_backoff_poison_message_and_dead_letter(
    client: TestClient, tenants: SeededTenants, session_factory: sessionmaker[Session]
):
    enqueued: list[int] = []
    app.dependency_overrides[get_enqueue_fn] = lambda: lambda ev_id, _cid: enqueued.append(ev_id)
    admin_headers = login_client(client, tenants.a_admin.email)
    integration = _setup_live_integration(client, admin_headers)

    body = json.dumps(build_sample_alertmanager_payload()).encode("utf-8")
    sig = sign_webhook_payload(body, integration["signing_secret"])
    client.post(
        integration["webhook_path"],
        content=body,
        headers={"Content-Type": "application/json", SIGNATURE_HEADER: sig},
    )
    event_id = enqueued[0]

    # Simulate transient worker crashes until max_attempts -> dead_letter
    def crash(_db: Session, _ev: InboundEvent) -> None:
        raise RuntimeError("transient db blip")

    with session_factory() as db:
        out1 = ingestion_service.execute_event_processing(db, event_id=event_id, processor_fn=crash)
        assert out1.status is InboundEventStatus.RETRYING
        assert out1.retry_countdown_seconds is not None and out1.retry_countdown_seconds >= 2

        out2 = ingestion_service.execute_event_processing(db, event_id=event_id, processor_fn=crash)
        assert out2.status is InboundEventStatus.RETRYING

        out3 = ingestion_service.execute_event_processing(db, event_id=event_id, processor_fn=crash)
        assert out3.status is InboundEventStatus.DEAD_LETTER

    # Poison normalized payload -> goes straight to dead_letter on attempt 1
    body2 = json.dumps(build_sample_alertmanager_payload(scenario="queue_backlog")).encode("utf-8")
    client.post(
        integration["webhook_path"],
        content=body2,
        headers={
            "Content-Type": "application/json",
            SIGNATURE_HEADER: sign_webhook_payload(body2, integration["signing_secret"]),
        },
    )
    poison_id = enqueued[1]
    with session_factory() as db:
        ev = db.get(InboundEvent, poison_id)
        assert ev is not None
        ev.normalized_payload_json = {"corrupted": True}
        db.commit()
        poison_out = ingestion_service.execute_event_processing(db, event_id=poison_id)
        assert poison_out.status is InboundEventStatus.DEAD_LETTER


def test_simulator_is_distinguishable_and_never_shows_connected(
    client: TestClient, tenants: SeededTenants, session_factory: sessionmaker[Session]
):
    enqueued: list[int] = []
    app.dependency_overrides[get_enqueue_fn] = lambda: lambda ev_id, _cid: enqueued.append(ev_id)
    admin_headers = login_client(client, tenants.a_admin.email)

    sim_cfg = client.post(
        "/api/v1/integrations",
        json={"provider": "alertmanager", "name": "Local Simulator", "is_simulator_mode": True},
        headers=admin_headers,
    ).json()
    assert sim_cfg["connection_status"] == "simulator"

    sim_resp = client.post(
        f"/api/v1/integrations/{sim_cfg['id']}/simulate",
        json={"scenario": "high_error_rate", "status": "firing"},
        headers=admin_headers,
    )
    assert sim_resp.status_code == 202
    with session_factory() as db:
        ingestion_service.execute_event_processing(db, event_id=enqueued[0])

    incidents = client.get("/api/v1/incidents").json()
    assert incidents[0]["source"] == "alertmanager-simulator"
    assert incidents[0]["metadata"]["simulated"] is True

    # Tenant B cannot view or replay Tenant A's integration or events
    b_headers = login_client(client, tenants.b_owner.email)
    assert client.get("/api/v1/integrations").json() == []
    assert client.get("/api/v1/events").json() == []
    assert client.get(f"/api/v1/events/{enqueued[0]}").status_code == 404
    assert client.post(f"/api/v1/events/{enqueued[0]}/replay", headers=b_headers).status_code == 404
