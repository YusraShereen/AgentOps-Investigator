import json
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from agentic_ai_portfolio.agentops.tools import (
    get_service_metrics,
    search_recent_logs,
)


class IncidentState(TypedDict):
    incident_id: str
    service: str
    severity: str
    description: str
    approve_remediation: bool
    attempts: int
    findings: list[str]
    status: str
    remediation: str
    audit_log: list[str]
    telemetry_available: bool
    observed_facts: list[str]
    inferred_causes: list[str]
    unresolved_uncertainties: list[str]
    trace_events: list[dict]


MAX_ATTEMPTS = 3

def investigate(state: IncidentState) -> dict:
    attempt = state["attempts"] + 1

    metrics_result = json.loads(
        get_service_metrics.invoke({"service": state["service"]})
    )
    logs_result = json.loads(
        search_recent_logs.invoke({"service": state["service"]})
    )

    metrics_available = "error" not in metrics_result
    logs_available = "error" not in logs_result

    findings = []
    observed_facts = []
    inferred_causes = []
    unresolved_uncertainties = []

    if metrics_available:
        metrics = metrics_result["metrics"]

        observed_facts.extend([
            f"Latency: {metrics['latency_ms']} ms",
            f"Error rate: {metrics['error_rate_pct']}%",
            f"CPU usage: {metrics['cpu_usage_pct']}%",
        ])

        findings.extend([
            f"Observed latency: {metrics['latency_ms']} ms",
            f"Observed error rate: {metrics['error_rate_pct']}%",
            f"Observed CPU usage: {metrics['cpu_usage_pct']}%",
        ])

        if metrics["latency_ms"] > 1000:
            findings.append("Evidence: elevated service latency")
            inferred_causes.append(
                "A slow dependency or resource bottleneck may "
                "contribute to elevated latency; this is unconfirmed."
            )

        if metrics["error_rate_pct"] > 5:
            findings.append("Evidence: elevated application error rate")
            inferred_causes.append(
                "An application or upstream dependency failure "
                "may contribute to the elevated error rate."
            )

        if metrics["cpu_usage_pct"] > 85:
            findings.append("Evidence: high CPU utilization")
            inferred_causes.append(
                "Resource saturation may contribute to the incident."
            )
    else:
        findings.append(
            "Metrics unavailable: no reliable metric evidence"
        )
        unresolved_uncertainties.append(
            "Service metrics are unavailable."
        )

    if logs_available:
        logs = logs_result["logs"]

        for log in logs:
            if "ERROR" in log or "WARN" in log:
                findings.append(f"Log evidence: {log}")
                observed_facts.append(f"Log entry: {log}")

                if "database connection pool near capacity" in log.lower():
                    inferred_causes.append(
                        "Database connection pool saturation may "
                        "contribute to the incident; this is unconfirmed."
                    )
    else:
        findings.append(
            "Logs unavailable: no reliable log evidence"
        )
        unresolved_uncertainties.append(
            "Recent application logs are unavailable."
        )

    has_evidence = any(
        item.startswith(("Evidence:", "Log evidence:"))
        for item in findings
    )

    if (
        metrics_available
        and logs_available
        and not has_evidence
    ):
        findings.append(
            "No configured anomaly threshold was exceeded"
        )

    if has_evidence and not inferred_causes:
        unresolved_uncertainties.append(
            "The available evidence does not establish a root cause."
        )

    if not metrics_available or not logs_available:
        unresolved_uncertainties.append(
            "The investigation is limited by incomplete telemetry."
        )

    return {
        "attempts": attempt,
        "findings": findings,
        "observed_facts": observed_facts,
        "inferred_causes": inferred_causes,
        "unresolved_uncertainties": unresolved_uncertainties,
        "audit_log": [
            *state["audit_log"],
            f"Diagnostic tools executed on attempt {attempt}",
            f"Metrics available: {metrics_available}",
            f"Logs available: {logs_available}",
        ],
        "telemetry_available": metrics_available and logs_available,
	"trace_events": [
	    *state["trace_events"],
	    {
	        "event": "diagnostic_attempt_completed",
	        "incident_id": state["incident_id"],
	        "attempt": attempt,
	        "outcome": (
	            "telemetry_complete"
	            if metrics_available and logs_available
	            else "telemetry_incomplete"
	        ),
	    },
	],
    }


def assess(state: IncidentState) -> dict:
    sufficient = any(
        item.startswith(("Evidence:", "Log evidence:"))
        for item in state["findings"]
    )

    if sufficient:
        status = "investigated"
    elif state["telemetry_available"]:
        status = "no_anomaly_detected"
    elif state["attempts"] >= MAX_ATTEMPTS:
        status = "insufficient_evidence"
    else:
        status = "retrying"

    return {
	    "status": status,
	    "audit_log": [
	        *state["audit_log"],
	        f"Evidence assessment: {status}",
	    ],
	    "trace_events": [
	        *state["trace_events"],
	        {
	            "event": "assessment_completed",
	            "incident_id": state["incident_id"],
	            "attempt": state["attempts"],
	            "outcome": status,
	        },
	    ],
	}

def route_after_assessment(state: IncidentState) -> str:
    if state["status"] == "retrying":
        return "investigate"
    if state["status"] == "investigated":
        return "approval_gate"
    return "finish"


def approval_gate(state: IncidentState) -> dict:
    if state["approve_remediation"]:
        status = "approved_for_mock_remediation"
        remediation = (
            "Mock remediation approved; no real system was changed."
        )
        audit_entries = [
            "Remediation explicitly approved",
            "Mock remediation recorded; no external action taken",
        ]
    else:
        status = "awaiting_approval"
        remediation = "Not executed: explicit approval required."
        audit_entries = [
            "Remediation withheld pending explicit approval",
        ]
    return {
        "status": status,
        "remediation": remediation,
        "audit_log": [
            *state["audit_log"],
            *audit_entries,
        ],
        "trace_events": [
            *state["trace_events"],
            {
                "event": "remediation_decision_recorded",
                "incident_id": state["incident_id"],
                "attempt": state["attempts"],
                "outcome": status,
            },
            {
                "event": "investigation_finished",
                "incident_id": state["incident_id"],
                "attempt": state["attempts"],
                "outcome": status,
            },
        ],
    }

def finish(state: IncidentState) -> dict:
    if state["status"] == "no_anomaly_detected":
        remediation = (
            "Not required: no configured anomaly threshold was exceeded."
        )
    else:
        remediation = (
            "Not executed: insufficient diagnostic evidence."
        )

    return {
        "remediation": remediation,
        "audit_log": [
            *state["audit_log"],
            f"Investigation finished with status: {state['status']}",
            "No external action taken",
        ],
        "trace_events": [
            *state["trace_events"],
            {
                "event": "investigation_finished",
                "incident_id": state["incident_id"],
                "attempt": state["attempts"],
                "outcome": state["status"],
            },
        ],
    }

def build_graph():
    workflow = StateGraph(IncidentState)

    workflow.add_node("investigate", investigate)
    workflow.add_node("assess", assess)
    workflow.add_node("approval_gate", approval_gate)
    workflow.add_node("finish", finish)

    workflow.add_edge(START, "investigate")
    workflow.add_edge("investigate", "assess")
    workflow.add_conditional_edges(
        "assess",
        route_after_assessment,
        {
            "investigate": "investigate",
            "approval_gate": "approval_gate",
            "finish": "finish",
        },
    )
    workflow.add_edge("approval_gate", END)
    workflow.add_edge("finish", END)

    return workflow.compile()


incident_graph = build_graph()


def investigate_incident(payload: dict) -> dict:
    initial_state: IncidentState = {
        **payload,
        "attempts": 0,
        "findings": [],
        "status": "received",
        "remediation": "Not attempted",
        "observed_facts": [],
        "inferred_causes": [],
        "unresolved_uncertainties": [],
        "audit_log": [
            f"Incident {payload['incident_id']} received",
        ],
        "telemetry_available": False,
        "trace_events": [{"event": "incident_received","incident_id": payload["incident_id"],"attempt": 0,"outcome": "started",}],
    }

    return incident_graph.invoke(initial_state)
