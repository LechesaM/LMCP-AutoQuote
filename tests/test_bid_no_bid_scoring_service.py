from __future__ import annotations

import importlib


def test_bid_no_bid_scoring_service_scores_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.bid_no_bid_scoring_service")
    service = module.BidNoBidScoringService(runtime_dir=tmp_path / "runtime" / "staging" / "tender-strategy-governance")
    tender = {
        "rfq_id": "RFQ-TS-001",
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

    analysis = service.score_bid_no_bid(tender, record_history=True)
    latest = service.latest_bid_no_bid_scoring()
    history = service.bid_no_bid_scoring_history(limit=5)

    assert analysis["bid_no_bid_readiness"]["ready"] is True
    assert analysis["tender_attractiveness_score"] >= 0.0
    assert analysis["win_probability_estimate"] >= 0.0
    assert analysis["strategic_fit_score"] >= 0.0
    assert analysis["risk_adjusted_opportunity_score"] >= 0.0
    assert analysis["executive_review_required"] is True
    assert analysis["mandatory_document_readiness"]["ready"] is True
    assert analysis["strategy_rules"]["autonomous_bid_submission_enabled"] is False
    assert analysis["strategy_rules"]["auto_bid_no_bid_approval_enabled"] is False
    assert analysis["strategy_rules"]["production_submission_authority_enabled"] is False
    assert analysis["strategy_rules"]["procurement_commitment_generation_enabled"] is False
    assert analysis["strategy_rules"]["live_tender_portal_credentials_present"] is False
    assert latest["status"] in {"ok", "watch"}
    assert history["count"] >= 1
