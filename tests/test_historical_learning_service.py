from __future__ import annotations

import importlib


def test_historical_learning_service_aggregates_outcome_intelligence_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.historical_learning_service")
    service = module.HistoricalLearningService(runtime_dir=tmp_path / "runtime" / "staging" / "historical-learning-governance")

    latest = service.latest_historical_learning()
    history = service.historical_learning_history(limit=5)

    assert latest["ready"] is True
    assert latest["status"] == "ok"
    assert latest["historical_learning_readiness"]["ready"] is True
    assert latest["tender_outcome_learning_readiness"]["ready"] is True
    assert latest["supplier_memory_readiness"]["ready"] is True
    assert latest["pricing_calibration_readiness"]["ready"] is True
    assert latest["win_loss_analytics_readiness"]["ready"] is True
    assert latest["confidence_recalibration_readiness"]["ready"] is True
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
