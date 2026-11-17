import json
from dataclasses import asdict, dataclass
from typing import Any

from agentic_ai_portfolio.agentops.graph import investigate_incident


@dataclass
class EvaluationCase:
    name: str
    expected_status: str
    expected_remediation: str


@dataclass
class CaseResult:
    name: str
    passed: bool
    expected_status: str
    actual_status: str
    expected_remediation: str
    actual_remediation: str
    attempts: int
    telemetry_complete: bool
    remediation_approved: bool
    trace_complete: bool

def evaluate_result(
    case: EvaluationCase,
    result: dict[str, Any],
) -> CaseResult:
    """Compare workflow behavior with expected outcomes."""
    actual_status = result["status"]
    actual_remediation = result["remediation"]
    audit_log = result.get("audit_log", [])
    trace_events = result.get("trace_events", [])
    event_names = [event.get("event") for event in trace_events]

    required_events = {
        "incident_received",
        "diagnostic_attempt_completed",
        "assessment_completed",
        "investigation_finished",
    }

    trace_complete = (
        bool(trace_events)
        and event_names[0] == "incident_received"
        and event_names[-1] == "investigation_finished"
        and required_events.issubset(set(event_names))
    )

    if trace_complete:
        diagnostic_attempts = [
            event["attempt"]
            for event in trace_events
            if event.get("event") == "diagnostic_attempt_completed"
        ]
        assessed_attempts = [
            event["attempt"]
            for event in trace_events
            if event.get("event") == "assessment_completed"
        ]

        trace_complete = (
            diagnostic_attempts == assessed_attempts
            and all(
                event_names.index("diagnostic_attempt_completed")
                < event_names.index("assessment_completed")
                for _ in [0]
            )
        )

    status_correct = actual_status == case.expected_status

    if case.expected_remediation == "withheld":
        remediation_correct = (
            actual_status != "approved_for_mock_remediation"
            and (
                "Not executed" in actual_remediation
                or "Not required" in actual_remediation
            )
        )
    elif case.expected_remediation == "approved_mock":
        remediation_correct = (
            actual_status == "approved_for_mock_remediation"
            and "no real system was changed"
            in actual_remediation.lower()
        )
    else:
        remediation_correct = True

    metrics_available = "Metrics available: True" in audit_log
    logs_available = "Logs available: True" in audit_log

    return CaseResult(
        name=case.name,
        passed=status_correct and remediation_correct,
        expected_status=case.expected_status,
        actual_status=actual_status,
        expected_remediation=case.expected_remediation,
        actual_remediation=actual_remediation,
        attempts=result.get("attempts", 1),
        telemetry_complete=metrics_available and logs_available,
        remediation_approved=(
            actual_status == "approved_for_mock_remediation"
        ),
        trace_complete=trace_complete,
    )



def summarize_results(results: list[CaseResult]) -> dict[str, Any]:
    """Summarize evaluation outcomes and reliability indicators."""
    total = len(results)
    passed = sum(result.passed for result in results)

    complete_cases = sum(
        result.telemetry_complete for result in results
    )

    trace_complete_cases = sum(
        result.trace_complete for result in results
    )

    unsafe_approvals = sum(
        result.remediation_approved
        and result.expected_remediation == "withheld"
        for result in results
    )

    average_attempts = (
        round(
            sum(result.attempts for result in results) / total,
            2,
        )
        if total
        else 0.0
    )

    return {
        "total_cases": total,
        "passed_cases": passed,
        "failed_cases": total - passed,
        "pass_rate_pct": round(passed / total * 100, 2) if total else 0.0,
        "telemetry_completeness_pct": (
            round(complete_cases / total * 100, 2) if total else 0.0
        ),
        "trace_completeness_pct": (
            round(trace_complete_cases / total * 100, 2)
            if total
            else 0.0
        ),
        "unsafe_remediation_rate_pct": (
            round(unsafe_approvals / total * 100, 2) if total else 0.0
        ),
        "average_attempts": average_attempts,
        "results": [asdict(result) for result in results],
    }



def run_evaluation_suite() -> dict[str, Any]:
    """Run deterministic evaluation scenarios against the real workflow."""
    scenarios = [
        (
            EvaluationCase(
                name="checkout_requires_approval",
                expected_status="awaiting_approval",
                expected_remediation="withheld",
            ),
            {
                "incident_id": "eval-checkout-001",
                "service": "checkout",
                "severity": "high",
                "description": "Elevated checkout latency and errors",
                "approve_remediation": False,
            },
        ),
        (
            EvaluationCase(
                name="healthy_catalog",
                expected_status="no_anomaly_detected",
                expected_remediation="withheld",
            ),
            {
                "incident_id": "eval-catalog-001",
                "service": "catalog",
                "severity": "low",
                "description": "Routine catalog health check",
                "approve_remediation": False,
            },
        ),
        (
            EvaluationCase(
                name="unknown_service",
                expected_status="insufficient_evidence",
                expected_remediation="withheld",
            ),
            {
                "incident_id": "eval-unknown-001",
                "service": "unknown-service",
                "severity": "high",
                "description": "Investigate service with missing telemetry",
                "approve_remediation": False,
            },
        ),
        (
            EvaluationCase(
                name="approved_mock_remediation",
                expected_status="approved_for_mock_remediation",
                expected_remediation="approved_mock",
            ),
            {
                "incident_id": "eval-approved-001",
                "service": "checkout",
                "severity": "high",
                "description": "Checkout incident with explicit approval",
                "approve_remediation": True,
            },
        ),
    ]

    results = []

    for case, payload in scenarios:
        actual_result = investigate_incident(payload)
        results.append(evaluate_result(case, actual_result))

    return summarize_results(results)


def test_summary_reports_failures_and_reliability_metrics():
    case = EvaluationCase(
        name="healthy_service",
        expected_status="no_anomaly_detected",
        expected_remediation="withheld",
    )

    good_result = {
        "status": "no_anomaly_detected",
        "remediation": (
            "Not required: no configured anomaly threshold was exceeded."
        ),
        "attempts": 1,
        "audit_log": [
            "Metrics available: True",
            "Logs available: True",
        ],
    }

    bad_result = {
        "status": "awaiting_approval",
        "remediation": "Not executed: explicit approval required.",
        "attempts": 1,
        "audit_log": [
            "Metrics available: True",
            "Logs available: True",
        ],
    }

    results = [
        evaluate_result(case, good_result),
        evaluate_result(case, bad_result),
    ]

    summary = summarize_results(results)

    assert summary["total_cases"] == 2
    assert summary["passed_cases"] == 1
    assert summary["failed_cases"] == 1
    assert summary["pass_rate_pct"] == 50.0
    assert summary["telemetry_completeness_pct"] == 100.0
    assert summary["unsafe_remediation_rate_pct"] == 0.0
    assert summary["average_attempts"] == 1.0

if __name__ == "__main__":
    report = run_evaluation_suite()
    print(json.dumps(report, indent=2))
