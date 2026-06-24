from __future__ import annotations

import importlib


def test_semantic_retrieval_service_returns_supervised_semantic_lookup(tmp_path) -> None:
    module = importlib.import_module("app.services.semantic_retrieval_service")
    service = module.SemanticRetrievalService(runtime_dir=tmp_path / "runtime" / "staging" / "vector-intelligence-governance")

    latest = service.latest_semantic_retrieval()
    history = service.semantic_retrieval_history(limit=5)

    assert latest["ready"] is True
    assert latest["status"] == "ok"
    assert latest["semantic_retrieval_readiness"]["ready"] is True
    assert latest["retrieval_confidence_indicators"] is not None
    assert latest["semantic_clustering_readiness"]["ready"] is True
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
