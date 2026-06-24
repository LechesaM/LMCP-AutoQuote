from __future__ import annotations

import importlib


def test_similarity_analysis_service_returns_similarity_memory_snapshot(tmp_path) -> None:
    module = importlib.import_module("app.services.similarity_analysis_service")
    service = module.SimilarityAnalysisService(runtime_dir=tmp_path / "runtime" / "staging" / "vector-intelligence-governance")

    latest = service.latest_similarity_analysis()
    history = service.similarity_analysis_history(limit=5)

    assert latest["ready"] is True
    assert latest["status"] == "ok"
    assert latest["similarity_analysis_readiness"]["ready"] is True
    assert latest["semantic_clustering_readiness"]["ready"] is True
    assert latest["retrieval_confidence_indicators"] is not None
    assert latest["autonomous_vector_decisioning_enabled"] is False
    assert latest["autonomous_procurement_execution_enabled"] is False
    assert latest["autonomous_supplier_selection_enabled"] is False
    assert latest["autonomous_pricing_override_enabled"] is False
    assert latest["production_vector_learning_enabled"] is False
    assert latest["dry_run_enforced"] is True
    assert latest["human_supervision_required"] is True
    assert latest["supervised_retrieval_review_required"] is True
    assert latest["embedding_governance_review_required"] is True
    assert history["count"] >= 1
