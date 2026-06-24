from __future__ import annotations

import importlib


def test_supplier_performance_memory_service_returns_governed_snapshot_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.supplier_performance_memory_service")
    service = module.SupplierPerformanceMemoryService(runtime_dir=tmp_path / "runtime" / "staging" / "historical-learning-governance")

    latest = service.latest_supplier_performance_memory()
    history = service.supplier_performance_memory_history(limit=5)

    assert latest["ready"] is True
    assert latest["status"] == "ok"
    assert latest["supplier_memory_readiness"]["ready"] is True
    assert latest["autonomous_learning_execution_enabled"] is False
    assert latest["autonomous_procurement_decision_updates_enabled"] is False
    assert latest["autonomous_supplier_blacklisting_enabled"] is False
    assert latest["autonomous_strategy_modification_enabled"] is False
    assert latest["production_learning_mode_enabled"] is False
    assert latest["dry_run_enforced"] is True
    assert latest["human_supervision_required"] is True
    assert latest["supervised_learning_review_required"] is True
    assert latest["executive_feedback_required"] is True
    assert latest["unresolved_learning_blockers"] is not None
    assert history["count"] >= 1
