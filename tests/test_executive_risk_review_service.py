from __future__ import annotations

import importlib


def test_executive_risk_review_service_returns_governed_snapshot_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.executive_risk_review_service")
    service = module.ExecutiveRiskReviewService(runtime_dir=tmp_path / "runtime" / "staging" / "executive-governance")

    latest = service.latest_executive_risk_review()
    history = service.executive_risk_review_history(limit=5)

    assert latest["status"] in {"ok", "watch"}
    assert latest["latest_executive_risk_review"]["financial_exposure_indicators"] is not None
    assert latest["latest_executive_risk_review"]["escalation_review_required"] is True
    assert history["count"] >= 1
