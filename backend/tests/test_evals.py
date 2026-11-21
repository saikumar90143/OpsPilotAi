"""Phase 10 tests: deterministic offline AI evaluation dataset and metrics."""

from app.evals.runner import run_evaluation


def test_offline_ai_evaluation_dataset_passes_thresholds():
    report = run_evaluation(live=False)

    assert report["dataset_version"] == "eval-dataset-v1.0"
    assert report["provider_mode"] == "mock"
    assert report["total_cases"] == 5
    assert report["citation_validity_rate"] == 1.0
    assert report["unsupported_claim_rate"] == 0.0
    assert report["uncertainty_f1"] == 1.0
    assert report["tool_selection_accuracy"] == 1.0
    assert report["retrieval_relevance_rate"] == 1.0
    assert len(report["cases"]) == 5
    assert all(c["citations_valid"] is True for c in report["cases"])
