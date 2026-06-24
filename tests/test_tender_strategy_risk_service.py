from __future__ import annotations

import importlib


def test_tender_strategy_risk_service_scores_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.tender_strategy_risk_service")
    service = module.TenderStrategyRiskService(runtime_dir=tmp_path / "runtime" / "staging" / "tender-strategy-governance")
    tender = {
        "rfq_id": "RFQ-TS-003",
        "title": "Supply and delivery of office stationery",
        "description": "Framework agreement for stationery and consumables.",
        "buyer_name": "Sample Municipality",
        "category": "supplies",
        "submission_method": "portal",
        "closing_date": "2026-06-30T00:00:00+00:00",
        "unit_price": 118.0,
        "quantity": 20,
        "unit": "Each",
        "vat_rate": 0.15,
        "markup_rate": 0.25,
    }

    analysis = service.assess_strategy_risk(tender, record_history=True)
    latest = service.latest_tender_strategy_risk()
    history = service.tender_strategy_risk_history(limit=5)

    assert analysis["risk_score"] >= 0.0
    assert analysis["strategic_fit_score"] >= 0.0
    assert analysis["risk_adjusted_opportunity_score"] >= 0.0
    assert analysis["executive_review_required"] is True
    assert latest["status"] in {"ok", "watch"}
    assert history["count"] >= 1
