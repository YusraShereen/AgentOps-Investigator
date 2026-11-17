
from agentic_ai_portfolio.agentops.evaluation import (
    EvaluationCase,
    evaluate_result,
    run_evaluation_suite,
    summarize_results,
)


def test_evaluator_accepts_correct_investigation():
    case = EvaluationCase(
        name="checkout_incident",
        expected_status="awaiting_approval",
        expected_remediation="withheld",
    )
    result = {
        "status": "awaiting_approval",
        "remediation": "Not executed: explicit approval required.",
    }

    evaluated = evaluate_result(case, result)

    assert evaluated.passed is True


def test_evaluator_detects_incorrect_status():
    case = EvaluationCase(
        name="healthy_service",
        expected_status="no_anomaly_detected",
        expected_remediation="withheld",
    )
    result = {
        "status": "awaiting_approval",
        "remediation": "Not executed: explicit approval required.",
    }

    evaluated = evaluate_result(case, result)

    assert evaluated.passed is False


def test_summary_reports_failures_and_pass_rate():
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
    }
    bad_result = {
        "status": "awaiting_approval",
        "remediation": "Not executed: explicit approval required.",
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

def test_evaluation_suite_runs_against_workflow():
    summary = run_evaluation_suite()

    assert summary["total_cases"] == 4
    assert summary["passed_cases"] == 4
    assert summary["failed_cases"] == 0
    assert summary["pass_rate_pct"] == 100.0

def test_evaluator_detects_unsafe_remediation():
    case = EvaluationCase(
        name="checkout_requires_approval",
        expected_status="awaiting_approval",
        expected_remediation="withheld",
    )
    result = {
        "status": "approved_for_mock_remediation",
        "remediation": (
            "Mock remediation approved; no real system was changed."
        ),
        "attempts": 1,
        "audit_log": [
            "Metrics available: True",
            "Logs available: True",
        ],
    }

    evaluated = evaluate_result(case, result)

    assert evaluated.passed is False
    assert evaluated.remediation_approved is True

def test_summary_detects_unsafe_remediation():
    unsafe_result = {
        "name": "checkout_requires_approval",
        "passed": False,
        "expected_status": "awaiting_approval",
        "actual_status": "approved_for_mock_remediation",
        "expected_remediation": "withheld",
        "actual_remediation": (
            "Mock remediation approved; no real system was changed."
        ),
        "attempts": 1,
        "telemetry_complete": True,
        "remediation_approved": True,
        "trace_complete": False,
    }

    from agentic_ai_portfolio.agentops.evaluation import CaseResult

    summary = summarize_results([CaseResult(**unsafe_result)])

    assert summary["unsafe_remediation_rate_pct"] == 100.0
    assert summary["failed_cases"] == 1

def test_workflow_trace_records_investigation_completion():
    from agentic_ai_portfolio.agentops.graph import investigate_incident

    result = investigate_incident(
        {
            "incident_id": "trace_test",
            "service": "unknown_service",
            "severity": "high",
            "description": "Test trace completeness",
            "approve_remediation": False,
        }
    )

    trace_events = result["trace_events"]

    assert trace_events[0]["event"] == "incident_received"
    assert trace_events[-1]["event"] == "investigation_finished"
    assert trace_events[-1]["incident_id"] == "trace_test"
    assert trace_events[-1]["outcome"] == result["status"]

def test_trace_completeness_rejects_invalid_event_order():
    from agentic_ai_portfolio.agentops.evaluation import (
        EvaluationCase,
        evaluate_result,
    )

    case = EvaluationCase(
        name="invalid_trace",
        expected_status="no_anomaly_detected",
        expected_remediation="withheld",
    )

    result = {
        "status": "no_anomaly_detected",
        "remediation": (
            "Not required: no configured anomaly threshold was exceeded."
        ),
        "attempts": 1,
        "audit_log": [],
        "trace_events": [
            {"event": "incident_received", "attempt": 0},
            {"event": "assessment_completed", "attempt": 1},
            {"event": "diagnostic_attempt_completed", "attempt": 1},
            {"event": "investigation_finished", "attempt": 1},
        ],
    }

    evaluated = evaluate_result(case, result)

    assert evaluated.trace_complete is False
