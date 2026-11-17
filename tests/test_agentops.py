
import json

from fastapi.testclient import TestClient

import agentic_ai_portfolio.agentops.graph as graph_module
from agentic_ai_portfolio.agentops.api import app
from agentic_ai_portfolio.agentops.graph import investigate_incident

client = TestClient(app)


def make_incident(**overrides):
    payload = {
        "incident_id": "INC-001",
        "service": "checkout",
        "severity": "high",
        "description": "Elevated latency and slow responses",
        "approve_remediation": False,
    }
    payload.update(overrides)
    return payload


def test_investigation_without_approval_does_not_remediate():
    result = investigate_incident(make_incident())

    assert result["status"] == "awaiting_approval"
    assert result["attempts"] == 1
    assert "Not executed" in result["remediation"]


def test_approved_remediation_is_mock_only():
    result = investigate_incident(
        make_incident(approve_remediation=True)
    )

    assert result["status"] == "approved_for_mock_remediation"
    assert "no real system was changed" in result["remediation"]


def test_insufficient_evidence_has_bounded_retries():
    result = investigate_incident(
        make_incident(
            service="unknown-service",
            description="Something unusual happened",
        )
    )

    assert result["status"] == "insufficient_evidence"
    assert result["attempts"] == 3
    assert "Not executed" in result["remediation"]
    assert result["attempts"] == 3
    assert result["status"] == "insufficient_evidence"
    assert result["telemetry_available"] is False
    assert "insufficient diagnostic evidence" in result["remediation"].lower()

    assert sum(
           entry == "Metrics available: False"
           for entry in result["audit_log"]
           ) == 3

    assert sum(
           entry == "Logs available: False"
           for entry in result["audit_log"]
           ) == 3

    assert not any(
           "Remediation explicitly approved" in entry
           for entry in result["audit_log"]
           )


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_investigation_api():
    response = client.post(
        "/incidents/investigate",
        json=make_incident(),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "awaiting_approval"

def test_healthy_service_does_not_request_remediation():
    result = investigate_incident(
        make_incident(
            service="catalog",
            description="Routine health check",
        )
    )

    assert result["status"] == "no_anomaly_detected"
    assert result["attempts"] == 1
    assert "Not required" in result["remediation"]

def test_log_evidence_is_used_when_metrics_are_unavailable(monkeypatch):
    class FakeTool:
        def __init__(self, result):
            self.result = result

        def invoke(self, _arguments):
            return json.dumps(self.result)

    monkeypatch.setattr(
        graph_module,
        "get_service_metrics",
        FakeTool({"service": "checkout", "error": "Metrics unavailable"}),
    )
    monkeypatch.setattr(
        graph_module,
        "search_recent_logs",
        FakeTool({
            "service": "checkout",
            "logs": ["ERROR: database connection failed"],
        }),
    )

    result = graph_module.investigate_incident(
        make_incident(approve_remediation=False)
    )

    assert result["status"] == "awaiting_approval"
    assert result["attempts"] == 1
    assert any(
        "Log evidence: ERROR: database connection failed" in finding
        for finding in result["findings"]
    )
    assert any(
        "Metrics available: False" in entry
        for entry in result["audit_log"]
    )
    assert any(
        "Logs available: True" in entry
        for entry in result["audit_log"]
    )
    assert "Not executed" in result["remediation"]

def test_metric_evidence_is_used_when_logs_are_unavailable(monkeypatch):
    class FakeTool:
        def __init__(self, result):
            self.result = result

        def invoke(self, _arguments):
            return json.dumps(self.result)

    monkeypatch.setattr(
        graph_module,
        "get_service_metrics",
        FakeTool({
            "service": "checkout",
            "metrics": {
                "latency_ms": 1800,
                "error_rate_pct": 1.0,
                "cpu_usage_pct": 40.0,
            },
        }),
    )
    monkeypatch.setattr(
        graph_module,
        "search_recent_logs",
        FakeTool({"service": "checkout", "error": "Logs unavailable"}),
    )

    result = graph_module.investigate_incident(
        make_incident(approve_remediation=False)
    )

    assert result["status"] == "awaiting_approval"
    assert result["attempts"] == 1
    assert "Evidence: elevated service latency" in result["findings"]
    assert any(
        "Metrics available: True" in entry
        for entry in result["audit_log"]
    )
    assert any(
        "Logs available: False" in entry
        for entry in result["audit_log"]
    )
    assert "Not executed" in result["remediation"]


def test_investigation_returns_structured_evidence():
    result = investigate_incident(
        make_incident(approve_remediation=False)
    )

    assert result["observed_facts"]
    assert result["inferred_causes"]
    assert isinstance(result["unresolved_uncertainties"], list)
    assert any(
        "Latency:" in fact
        for fact in result["observed_facts"]
    )
    assert any(
        "unconfirmed" in cause
        for cause in result["inferred_causes"]
    )


def test_missing_telemetry_is_reported_as_uncertainty(monkeypatch):
    class FakeTool:
        def __init__(self, result):
            self.result = result

        def invoke(self, _arguments):
            return json.dumps(self.result)

    monkeypatch.setattr(
        graph_module,
        "get_service_metrics",
        FakeTool({
            "service": "checkout",
            "error": "Metrics unavailable",
        }),
    )
    monkeypatch.setattr(
        graph_module,
        "search_recent_logs",
        FakeTool({
            "service": "checkout",
            "error": "Logs unavailable",
        }),
    )

    result = graph_module.investigate_incident(
        make_incident(approve_remediation=False)
    )

    assert result["status"] == "insufficient_evidence"
    assert result["attempts"] == 3
    assert any(
        "metrics are unavailable" in item.lower()
        for item in result["unresolved_uncertainties"]
    )
    assert any(
        "logs are unavailable" in item.lower()
        for item in result["unresolved_uncertainties"]
    )
    assert result["inferred_causes"] == []


def test_investigation_api_returns_structured_summary():
    client = TestClient(app)

    response = client.post(
        "/incidents/investigate",
        json=make_incident(approve_remediation=False),
    )

    assert response.status_code == 200

    data = response.json()

    assert "observed_facts" in data
    assert "inferred_causes" in data
    assert "unresolved_uncertainties" in data
    assert data["observed_facts"]
    assert isinstance(data["inferred_causes"], list)
    assert isinstance(data["unresolved_uncertainties"], list)


def test_investigation_api_rejects_invalid_severity():
    response = client.post(
        "/incidents/investigate",
        json=make_incident(severity="urgent"),
    )

    assert response.status_code == 422
