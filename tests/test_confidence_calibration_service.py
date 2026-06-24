from __future__ import annotations

import importlib


def test_confidence_calibration_service_returns_supervised_calibration_snapshot(tmp_path) -> None:
    module = importlib.import_module("app.services.confidence_calibration_service")
    service = module.ConfidenceCalibrationService(runtime_dir=tmp_path / "runtime" / "staging" / "recommendation-feedback-governance")

    latest = service.latest_confidence_calibration()
    history = service.confidence_calibration_history(limit=5)

    assert latest["ready"] is True
    assert latest["status"] == "ok"
    assert latest["confidence_calibration_readiness"]["ready"] is True
    assert latest["confidence_drift_indicators"] is not None
    assert latest["false_positive_negative_indicators"] is not None
    assert latest["autonomous_feedback_learning_enabled"] is False
    assert latest["autonomous_procurement_decision_updates_enabled"] is False
    assert latest["autonomous_supplier_ranking_updates_enabled"] is False
    assert latest["autonomous_pricing_override_enabled"] is False
    assert latest["autonomous_strategy_modification_enabled"] is False
    assert latest["production_calibration_mode_enabled"] is False
    assert latest["dry_run_enforced"] is True
    assert latest["human_supervision_required"] is True
    assert latest["supervised_calibration_review_required"] is True
    assert latest["analyst_feedback_review_required"] is True
    assert latest["executive_feedback_review_required"] is True
    assert history["count"] >= 1
