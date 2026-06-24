from __future__ import annotations

import importlib


def test_tender_win_probability_service_scores_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.tender_win_probability_service")
    service = module.TenderWinProbabilityService(runtime_dir=tmp_path / "runtime" / "staging" / "tender-strategy-governance")
    tender = {
        "rfq_id": "RFQ-TS-002",
        "title": "Supply and delivery of office stationery",
        "description": "Framework agreement for stationery and consumables.",
        "buyer_name": "Sample Municipality",
        "category": "supplies",
        "submission_method": "portal",
        "closing_date": "2026-06-30T00:00:00+00:00",
    }

    analysis = service.estimate_win_probability(tender, record_history=True)
    latest = service.latest_tender_win_probability()
    history = service.tender_win_probability_history(limit=5)

    assert analysis["win_probability_readiness"]["ready"] is True
    assert analysis["win_probability_estimate"] >= 0.0
    assert analysis["strategic_fit_score"] >= 0.0
    assert analysis["risk_adjusted_opportunity_score"] >= 0.0
    assert latest["status"] in {"ok", "watch"}
    assert history["count"] >= 1
