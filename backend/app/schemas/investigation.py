"""Pydantic v2 schemas for read-only AI investigation runs and structured reports."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.investigation import FeedbackRating


class AIStatusResponse(BaseModel):
    provider_mode: Literal["mock", "openai"]
    model_name: str
    configured: bool
    prompt_version: str
    max_graph_steps: int
    max_tool_calls: int
    tenant_daily_used: int
    tenant_daily_quota: int
    notice: str


class EvidenceBundleItem(BaseModel):
    evidence_id: str
    source_type: Literal["incident", "log", "github", "knowledge_base"]
    title: str
    timestamp: str | None = None
    url_or_uri: str | None = None
    summary: str
    is_synthetic: bool = False
    untrusted_content: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class ObservedFact(BaseModel):
    statement: str = Field(min_length=3, max_length=600)
    evidence_ids: list[str] = Field(min_length=1)


class PossibleCause(BaseModel):
    hypothesis: str = Field(min_length=3, max_length=600)
    confidence: Literal["high", "medium", "low"]
    rationale: str = Field(min_length=3, max_length=800)
    evidence_ids: list[str] = Field(default_factory=list)


class InvestigationReport(BaseModel):
    summary: str = Field(min_length=5, max_length=1500)
    insufficient_evidence: bool = False
    conflicting_evidence: bool = False
    observed_facts: list[ObservedFact] = Field(default_factory=list)
    possible_causes: list[PossibleCause] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    recommended_diagnostics: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)


class InvestigationStartRequest(BaseModel):
    window_hours: int = Field(default=24, ge=1, le=168)
    mock_scenario: Literal[
        "auto", "insufficient_evidence", "conflicting_evidence", "fabricated_citation"
    ] = "auto"


class InvestigationFeedbackRequest(BaseModel):
    rating: FeedbackRating
    note: str | None = Field(default=None, max_length=1000)


class InvestigationToolCallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    step_number: int
    tool_name: str
    status: str
    input_summary_json: dict[str, Any]
    output_count: int
    latency_ms: int
    error_message: str | None
    created_at: datetime


class InvestigationRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    incident_id: int
    requested_by_user_id: int | None
    status: str
    provider_mode: str
    model_name: str
    prompt_version: str
    window_hours: int
    graph_steps: int
    tool_calls_count: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float | None
    latency_ms: int
    evidence_bundle_json: list[EvidenceBundleItem]
    report_json: InvestigationReport | None
    error_message: str | None
    human_feedback_rating: str | None
    human_feedback_note: str | None
    feedback_by_user_id: int | None
    feedback_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    tool_calls: list[InvestigationToolCallOut] = Field(default_factory=list)
