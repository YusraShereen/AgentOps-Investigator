from typing import Literal

from pydantic import BaseModel, Field


class IncidentRequest(BaseModel):
    incident_id: str = Field(min_length=1, max_length=100)
    service: str = Field(min_length=1, max_length=100)
    severity: Literal["low", "medium", "high", "critical"]
    description: str = Field(min_length=1, max_length=2000)
    approve_remediation: bool = False


class InvestigationResult(BaseModel):
    incident_id: str
    status: str
    findings: list[str]
    observed_facts: list[str] = Field(default_factory=list)
    inferred_causes: list[str] = Field(default_factory=list)
    unresolved_uncertainties: list[str] = Field(default_factory=list)
    attempts: int
    remediation: str
    audit_log: list[str]
    trace_events: list[dict[str, str | int]]
