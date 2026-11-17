from fastapi import FastAPI

from agentic_ai_portfolio.agentops.graph import investigate_incident
from agentic_ai_portfolio.agentops.schemas import (
    IncidentRequest,
    InvestigationResult,
)

app = FastAPI(
    title="AgentOps",
    description="Auditable incident investigation with approval-gated mock remediation.",
    version="0.1.0",
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/incidents/investigate", response_model=InvestigationResult)
def investigate(request: IncidentRequest) -> InvestigationResult:
    result = investigate_incident(request.model_dump())
    return InvestigationResult(
        incident_id=request.incident_id,
        status=result["status"],
        findings=result["findings"],
        attempts=result["attempts"],
        remediation=result["remediation"],
        audit_log=result["audit_log"],
        trace_events=result["trace_events"],
        observed_facts=result["observed_facts"],
        inferred_causes=result["inferred_causes"],
        unresolved_uncertainties=result["unresolved_uncertainties"],
    )
