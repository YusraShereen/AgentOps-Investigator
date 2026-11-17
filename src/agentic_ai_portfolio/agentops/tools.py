import json

from langchain_core.tools import tool

# Simulated monitoring data for local development.
# These fixtures let us test the agent without real infrastructure.
SERVICE_METRICS = {
    "checkout": {
        "latency_ms": 1850,
        "error_rate_pct": 8.4,
        "cpu_usage_pct": 92.0,
    },
    "catalog": {
        "latency_ms": 120,
        "error_rate_pct": 0.2,
        "cpu_usage_pct": 35.0,
    },
    "payments": {
        "latency_ms": 780,
        "error_rate_pct": 4.5,
        "cpu_usage_pct": 76.0,
    },
}

SERVICE_LOGS = {
    "checkout": [
        "ERROR: request timeout after 5 seconds",
        "WARN: database connection pool near capacity",
        "ERROR: upstream dependency returned HTTP 503",
    ],
    "catalog": [
        "INFO: request completed successfully",
        "INFO: cache hit for product listing",
    ],
    "payments": [
        "WARN: payment provider response was slow",
        "ERROR: retry limit reached for payment request",
    ],
}


@tool
def get_service_metrics(service: str) -> str:
    """Retrieve simulated latency, error rate, and CPU metrics for a service."""
    metrics = SERVICE_METRICS.get(service)

    if metrics is None:
        return json.dumps({
            "service": service,
            "error": "No monitoring data available for this service.",
        })

    return json.dumps({
        "service": service,
        "metrics": metrics,
    })


@tool
def search_recent_logs(service: str) -> str:
    """Retrieve simulated recent application logs for a service."""
    logs = SERVICE_LOGS.get(service)

    if logs is None:
        return json.dumps({
            "service": service,
            "error": "No log data available for this service.",
        })

    return json.dumps({
        "service": service,
        "logs": logs,
    })
