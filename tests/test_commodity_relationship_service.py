from __future__ import annotations

import importlib


def test_commodity_relationship_service_returns_governed_snapshot(tmp_path) -> None:
    module = importlib.import_module("app.services.commodity_relationship_service")
    service = module.CommodityRelationshipService(runtime_dir=tmp_path / "runtime" / "staging" / "knowledge-graph-governance")

    latest = service.latest_commodity_relationship()
    history = service.commodity_relationship_history(limit=5)

    assert latest["ready"] is True
    assert latest["status"] == "ok"
    assert latest["commodity_relationship_readiness"]["ready"] is True
    assert latest["supplier_relationship_coverage"] is not None
    assert latest["department_relationship_coverage"] is not None
    assert latest["boq_to_pricing_relationship_coverage"] is not None
    assert latest["outcome_relationship_coverage"] is not None
    assert latest["autonomous_graph_decisioning_enabled"] is False
    assert latest["autonomous_supplier_ranking_updates_enabled"] is False
    assert latest["autonomous_pricing_override_enabled"] is False
    assert latest["autonomous_strategy_modification_enabled"] is False
    assert latest["autonomous_procurement_decisioning_enabled"] is False
    assert latest["production_graph_learning_enabled"] is False
    assert latest["dry_run_enforced"] is True
    assert latest["human_supervision_required"] is True
    assert latest["supervised_relationship_review_required"] is True
    assert latest["graph_governance_review_required"] is True
    assert history["count"] >= 1
