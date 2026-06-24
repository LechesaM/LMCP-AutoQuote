from __future__ import annotations

import importlib


def test_vector_intelligence_service_returns_supervised_semantic_memory_snapshot(tmp_path) -> None:
    module = importlib.import_module("app.services.vector_intelligence_service")
    service = module.VectorIntelligenceService(runtime_dir=tmp_path / "runtime" / "staging" / "vector-intelligence-governance")

    latest = service.latest_vector_intelligence()
    history = service.vector_intelligence_history(limit=5)

    assert latest["ready"] is True
    assert latest["status"] == "ok"
    assert latest["vector_intelligence_readiness"]["ready"] is True
    assert latest["semantic_retrieval_readiness"]["ready"] is True
    assert latest["contextual_memory_readiness"]["ready"] is True
    assert latest["similarity_analysis_readiness"]["ready"] is True
    assert latest["embedding_governance_readiness"]["ready"] is True
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
    assert latest["unresolved_vector_blockers"] is not None
    assert history["count"] >= 1
