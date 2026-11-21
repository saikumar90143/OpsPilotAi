"""Explicit, bounded LangGraph state machine for read-only AI investigations."""

from datetime import UTC, datetime, timedelta
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.ai.model_client import InvestigationModelClient, ModelSynthesisResult
from app.ai.tools import ToolExecutionRecord, execute_allowlisted_tool
from app.core.config import Settings
from app.models.incident import Incident
from app.models.investigation import InvestigationRun
from app.schemas.investigation import EvidenceBundleItem, InvestigationReport

TOOL_SEQUENCE: tuple[str, ...] = (
    "get_incident_history",
    "search_service_logs",
    "correlate_github_evidence",
    "search_knowledge_base",
)


class InvestigationState(TypedDict, total=False):
    graph_steps: int
    cancelled: bool
    evidence_bundle: list[EvidenceBundleItem]
    tool_records: list[ToolExecutionRecord]
    synthesis: ModelSynthesisResult
    validated_report: InvestigationReport
    error_message: str | None


def validate_report_citations(
    report: InvestigationReport, evidence_bundle: list[EvidenceBundleItem]
) -> str | None:
    """Return an error message if any cited evidence_id is missing from the bundle."""
    valid_ids = {item.evidence_id for item in evidence_bundle}
    cited: set[str] = set(report.citations)
    for fact in report.observed_facts:
        cited.update(fact.evidence_ids)
    for cause in report.possible_causes:
        cited.update(cause.evidence_ids)
    unknown = sorted(cited - valid_ids)
    if unknown:
        return f"Rejected fabricated or unknown evidence IDs: {', '.join(unknown)}"
    return None


def run_investigation_graph(
    *,
    db: Session,
    organization_id: int,
    incident: Incident,
    run: InvestigationRun,
    settings: Settings,
    model_client: InvestigationModelClient,
    mock_scenario: str = "auto",
    simulate_tool_timeout: bool = False,
) -> InvestigationState:
    """Execute the 5-node bounded LangGraph investigation state machine."""
    window_end = datetime.now(UTC)
    window_start = window_end - timedelta(hours=run.window_hours)

    def node_validate_and_load(state: InvestigationState) -> InvestigationState:
        db.refresh(run)
        if run.status == "cancelled":
            return {
                "graph_steps": state.get("graph_steps", 0) + 1,
                "cancelled": True,
                "error_message": "Investigation cancelled by user",
            }
        return {
            "graph_steps": state.get("graph_steps", 0) + 1,
            "cancelled": False,
            "evidence_bundle": [],
            "tool_records": [],
            "error_message": None,
        }

    def node_collect_evidence(state: InvestigationState) -> InvestigationState:
        if state.get("cancelled"):
            return {"graph_steps": state.get("graph_steps", 0) + 1}

        bundle: list[EvidenceBundleItem] = []
        records: list[ToolExecutionRecord] = []
        for idx, tool_name in enumerate(TOOL_SEQUENCE, start=1):
            if idx > settings.ai_max_tool_calls:
                break
            db.refresh(run)
            if run.status == "cancelled":
                return {
                    "graph_steps": state.get("graph_steps", 0) + 1,
                    "cancelled": True,
                    "evidence_bundle": bundle,
                    "tool_records": records,
                    "error_message": "Investigation cancelled during tool collection",
                }
            rec = execute_allowlisted_tool(
                tool_name,
                step_number=idx,
                db=db,
                organization_id=organization_id,
                incident=incident,
                window_start=window_start,
                window_end=window_end,
                settings=settings,
                simulate_timeout=(simulate_tool_timeout and tool_name == "search_service_logs"),
            )
            records.append(rec)
            bundle.extend(rec.items)

        return {
            "graph_steps": state.get("graph_steps", 0) + 1,
            "evidence_bundle": bundle,
            "tool_records": records,
        }

    def node_synthesize_report(state: InvestigationState) -> InvestigationState:
        if state.get("cancelled") or state.get("error_message"):
            return {"graph_steps": state.get("graph_steps", 0) + 1}
        bundle = state.get("evidence_bundle", [])
        try:
            res = model_client.synthesize(
                evidence_bundle=bundle,
                mock_scenario=mock_scenario,
            )
            return {
                "graph_steps": state.get("graph_steps", 0) + 1,
                "synthesis": res,
            }
        except Exception as exc:
            return {
                "graph_steps": state.get("graph_steps", 0) + 1,
                "error_message": f"{type(exc).__name__}: {exc}"[:400],
            }

    def node_validate_citations(state: InvestigationState) -> InvestigationState:
        if state.get("cancelled") or state.get("error_message"):
            return {"graph_steps": state.get("graph_steps", 0) + 1}
        synthesis = state.get("synthesis")
        if synthesis is None:
            return {
                "graph_steps": state.get("graph_steps", 0) + 1,
                "error_message": "Model returned no synthesis result",
            }
        err = validate_report_citations(synthesis.report, state.get("evidence_bundle", []))
        if err:
            return {
                "graph_steps": state.get("graph_steps", 0) + 1,
                "error_message": err,
            }
        return {
            "graph_steps": state.get("graph_steps", 0) + 1,
            "validated_report": synthesis.report,
        }

    builder: StateGraph[InvestigationState] = StateGraph(InvestigationState)
    builder.add_node("validate_and_load", node_validate_and_load)
    builder.add_node("collect_evidence", node_collect_evidence)
    builder.add_node("synthesize_report", node_synthesize_report)
    builder.add_node("validate_citations", node_validate_citations)

    builder.add_edge(START, "validate_and_load")
    builder.add_edge("validate_and_load", "collect_evidence")
    builder.add_edge("collect_evidence", "synthesize_report")
    builder.add_edge("synthesize_report", "validate_citations")
    builder.add_edge("validate_citations", END)

    compiled: Any = builder.compile()
    result: InvestigationState = compiled.invoke(
        {"graph_steps": 0},
        config={"recursion_limit": settings.ai_max_graph_steps},
    )
    return result
