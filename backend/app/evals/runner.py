"""Repeatable offline (and opt-in live) AI evaluation runner."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.database import Base
from app.core.permissions import Role
from app.core.security import hash_password
from app.models.github_connector import GitHubConnector
from app.models.incident import Incident
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.user import User
from app.schemas.investigation import InvestigationStartRequest
from app.services import evidence_service, investigation_service

DATASET_PATH = Path(__file__).resolve().parent / "dataset_v1.json"


def run_evaluation(*, live: bool = False) -> dict[str, Any]:
    """Execute the evaluation dataset in an isolated in-memory DB and return metrics."""
    payload = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    dataset_version = str(payload["dataset_version"])
    cases: list[dict[str, Any]] = payload["cases"]

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False)

    cfg = Settings(
        app_env="test",
        ai_provider_mode="openai" if live else "mock",
        ai_tenant_daily_quota=500,
    )

    tp = fp = fn = 0
    valid_citation_cases = 0
    total_citation_coverage = 0.0
    total_retrieval_relevance = 0.0
    total_tool_accuracy = 0.0
    unsupported_claim_cases = 0
    latencies: list[int] = []
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost_usd = 0.0
    case_results: list[dict[str, Any]] = []

    try:
        with Session() as db:
            org = Organization(name="Eval Org", slug="eval-org")
            user = User(
                email="eval@opspilot.local",
                full_name="Eval Runner",
                password_hash=hash_password("EvalPass123!"),
            )
            db.add_all([org, user])
            db.flush()
            db.add(Membership(organization_id=org.id, user_id=user.id, role=Role.ADMIN.value))
            db.commit()

            logs_seeded = False
            kb_seeded = False
            gh_seeded = False

            for case in cases:
                target_org_id = org.id
                if case.get("isolated_tenant"):
                    iso_org = Organization(
                        name=f"Eval Isolated {case['case_id']}",
                        slug=f"eval-{case['case_id']}",
                    )
                    db.add(iso_org)
                    db.flush()
                    db.add(
                        Membership(
                            organization_id=iso_org.id, user_id=user.id, role=Role.ADMIN.value
                        )
                    )
                    db.commit()
                    target_org_id = iso_org.id
                else:
                    if case.get("seed_logs") and not logs_seeded:
                        evidence_service.load_synthetic_logs(
                            db, organization_id=org.id, actor_user_id=user.id, settings=cfg
                        )
                        logs_seeded = True
                    if case.get("seed_kb") and not kb_seeded:
                        evidence_service.load_synthetic_runbooks(
                            db, organization_id=org.id, actor_user_id=user.id, settings=cfg
                        )
                        kb_seeded = True
                    if case.get("seed_github_mock") and not gh_seeded:
                        db.add(
                            GitHubConnector(
                                organization_id=org.id,
                                name="Eval Mock GitHub",
                                mode="mock",
                                auth_type="mock",
                                webhook_endpoint_token="eval-mock-token",
                                service_repo_map_json={"checkout-api": "acme/checkout-api"},
                            )
                        )
                        db.commit()
                        gh_seeded = True

                inc = Incident(
                    organization_id=target_org_id,
                    created_by_user_id=user.id,
                    title=case["title"],
                    description=case["description"],
                    service=case["service"],
                    environment="production",
                    severity=case["expected_severity"],
                    status="open",
                )
                db.add(inc)
                db.commit()
                db.refresh(inc)

                run = investigation_service.start_investigation(
                    db,
                    organization_id=target_org_id,
                    actor_user_id=user.id,
                    incident_id=inc.id,
                    data=InvestigationStartRequest(
                        window_hours=24,
                        mock_scenario=case.get("mock_scenario", "auto"),
                    ),
                    settings=cfg,
                )

                latencies.append(run.latency_ms)
                total_input_tokens += run.input_tokens
                total_output_tokens += run.output_tokens
                total_cost_usd += float(run.estimated_cost_usd or 0.0)

                report = run.report_json or {}
                bundle_ids = {item["evidence_id"] for item in run.evidence_bundle_json}
                bundle_types = {item["source_type"] for item in run.evidence_bundle_json}
                used_tools = {tc.tool_name for tc in run.tool_calls}

                # Uncertainty classification (insufficient_evidence)
                pred_unc = bool(report.get("insufficient_evidence", False))
                exp_unc = bool(case["expected_insufficient_evidence"])
                if pred_unc and exp_unc:
                    tp += 1
                elif pred_unc and not exp_unc:
                    fp += 1
                elif not pred_unc and exp_unc:
                    fn += 1

                # Citation validity & unsupported-claim check
                cited = set(report.get("citations", []))
                for fact in report.get("observed_facts", []):
                    cited.update(fact.get("evidence_ids", []))
                forbidden = set(case.get("forbidden_evidence_ids", []))
                citations_valid = (
                    bool(cited) and cited.issubset(bundle_ids) and not (cited & forbidden)
                )
                if citations_valid:
                    valid_citation_cases += 1
                else:
                    unsupported_claim_cases += 1

                facts = report.get("observed_facts", [])
                covered_facts = sum(1 for f in facts if f.get("evidence_ids"))
                total_citation_coverage += (covered_facts / len(facts)) if facts else 0.0

                exp_types = set(case["expected_evidence_types"])
                total_retrieval_relevance += (
                    len(exp_types & bundle_types) / len(exp_types) if exp_types else 1.0
                )

                exp_tools = set(case["expected_tools"])
                total_tool_accuracy += (
                    len(exp_tools & used_tools) / len(exp_tools) if exp_tools else 1.0
                )

                case_results.append(
                    {
                        "case_id": case["case_id"],
                        "status": run.status,
                        "citations_valid": citations_valid,
                        "insufficient_evidence": pred_unc,
                        "conflicting_evidence": bool(report.get("conflicting_evidence", False)),
                        "latency_ms": run.latency_ms,
                    }
                )
    finally:
        engine.dispose()

    n = len(cases)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {
        "dataset_version": dataset_version,
        "evaluated_at": datetime.now(UTC).isoformat(),
        "provider_mode": cfg.ai_provider_mode,
        "model_name": cfg.openai_model if live else "mock-deterministic-v1",
        "total_cases": n,
        "uncertainty_precision": round(precision, 4),
        "uncertainty_recall": round(recall, 4),
        "uncertainty_f1": round(f1, 4),
        "citation_validity_rate": round(valid_citation_cases / n, 4),
        "citation_coverage_rate": round(total_citation_coverage / n, 4),
        "retrieval_relevance_rate": round(total_retrieval_relevance / n, 4),
        "tool_selection_accuracy": round(total_tool_accuracy / n, 4),
        "unsupported_claim_rate": round(unsupported_claim_cases / n, 4),
        "mean_latency_ms": round(sum(latencies) / n, 2),
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_estimated_cost_usd": round(total_cost_usd, 6),
        "cases": case_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run OpsPilot AI evaluation dataset.")
    parser.add_argument("--live", action="store_true", help="Use live OpenAI Responses API")
    parser.add_argument("--output", type=str, default=None, help="Output JSON report path")
    args = parser.parse_args()

    report = run_evaluation(live=args.live)
    date_tag = datetime.now(UTC).strftime("%Y-%m-%d")
    out_path = Path(args.output or f"eval_report_{date_tag}.json")
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
