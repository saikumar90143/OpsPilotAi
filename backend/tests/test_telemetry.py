"""Phase 10 tests: OpenTelemetry tracing, Prometheus /metrics, cardinality, and JSON logs."""

import json
import logging

from fastapi.testclient import TestClient

from app.core.logging import JsonFormatter, RequestContextFilter
from app.core.telemetry import get_recent_ai_traces, get_tracer
from tests.conftest import TEST_PASSWORD, login_client


def test_prometheus_metrics_and_cardinality_control(client: TestClient, tenants):
    eng_headers = login_client(client, "eng@acme.local", TEST_PASSWORD)

    inc_resp = client.post(
        "/api/v1/incidents",
        headers=eng_headers,
        json={
            "title": "Telemetry test incident",
            "description": "Testing TTA/TTR and AI metrics",
            "service": "checkout-api",
            "environment": "production",
            "severity": "high",
        },
    )
    assert inc_resp.status_code == 201
    inc = inc_resp.json()

    # Acknowledge & resolve to emit TTA and TTR metrics
    ack_resp = client.post(
        f"/api/v1/incidents/{inc['id']}/acknowledge",
        headers=eng_headers,
        json={"version": inc["version"]},
    )
    assert ack_resp.status_code == 200
    res_resp = client.post(
        f"/api/v1/incidents/{inc['id']}/resolve",
        headers=eng_headers,
        json={"version": ack_resp.json()["version"]},
    )
    assert res_resp.status_code == 200

    # Run an AI investigation to emit AI metrics + local AI trace metadata
    inv_resp = client.post(
        f"/api/v1/incidents/{inc['id']}/investigations",
        headers=eng_headers,
        json={"window_hours": 24},
    )
    assert inv_resp.status_code == 201

    metrics_resp = client.get("/metrics")
    assert metrics_resp.status_code == 200
    body = metrics_resp.text

    assert "opspilot_http_requests_total" in body
    assert "opspilot_http_request_duration_seconds" in body
    assert "opspilot_incident_tta_seconds" in body
    assert "opspilot_incident_ttr_seconds" in body
    assert "opspilot_ai_investigation_duration_seconds" in body
    assert "opspilot_ai_investigation_tool_calls_total" in body
    assert "opspilot_ai_model_tokens_total" in body

    # Cardinality guard: raw user_id / incident_id / secrets must never appear as metric labels
    assert "user_id=" not in body
    assert "incident_id=" not in body
    assert TEST_PASSWORD not in body

    traces = get_recent_ai_traces()
    assert len(traces) >= 1
    assert traces[-1]["trace_id"] is not None


def test_json_logs_include_otel_trace_id_and_redact_secrets():
    tracer = get_tracer("opspilot.test")
    formatter = JsonFormatter()
    filt = RequestContextFilter()

    with tracer.start_as_current_span("test.span"):
        record = logging.LogRecord(
            name="app.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Calling postgresql+psycopg://u:topsecret@host:5432/db",
            args=(),
            exc_info=None,
        )
        filt.filter(record)
        parsed = json.loads(formatter.format(record))

    assert "trace_id" in parsed
    assert len(parsed["trace_id"]) == 32
    assert "topsecret" not in parsed["message"]
