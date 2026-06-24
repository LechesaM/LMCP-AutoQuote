from __future__ import annotations

import importlib


class _DummyLifecycleService:
    def __init__(self, items):
        self._items = items

    def list_items(self, state=None, limit=250):
        return {"status": "ok", "count": len(self._items), "items": self._items[:limit]}


def test_tender_strategy_governance_service_returns_governed_snapshot_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.tender_strategy_governance_service")
    service = module.TenderStrategyGovernanceService(runtime_dir=tmp_path / "runtime" / "staging" / "tender-strategy-governance")
    service.lifecycle = _DummyLifecycleService(
        [
            {
                "rfq_id": "RFQ-TS-004",
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
        ]
    )

    latest = service.latest_tender_strategy_governance()
    history = service.tender_strategy_governance_history(limit=5)

    assert latest["status"] in {"ok", "watch"}
    assert latest["bid_no_bid_readiness"]["ready"] is True
    assert latest["tender_attractiveness_score"] >= 0.0
    assert latest["win_probability_estimate"] >= 0.0
    assert latest["strategic_fit_score"] >= 0.0
    assert latest["pricing_competitiveness_alignment"] >= 0.0
    assert latest["supplier_readiness_alignment"] >= 0.0
    assert latest["compliance_readiness_alignment"] >= 0.0
    assert latest["risk_adjusted_opportunity_score"] >= 0.0
    assert latest["executive_review_required"] is True
    assert latest["governance_rules"]["autonomous_bid_submission_enabled"] is False
    assert latest["governance_rules"]["auto_bid_no_bid_approval_enabled"] is False
    assert latest["governance_rules"]["production_submission_authority_enabled"] is False
    assert latest["governance_rules"]["procurement_commitment_generation_enabled"] is False
    assert latest["governance_rules"]["live_tender_portal_credentials_present"] is False
    assert latest["governance_rules"]["dry_run_enforced"] is True
    assert latest["governance_rules"]["supervision_mandatory"] is True
    assert latest["governance_rules"]["bid_no_bid_human_approval_required"] is True
    assert latest["governance_rules"]["executive_review_required"] is True
    assert history["count"] >= 1
