from __future__ import annotations

import importlib


class _DummyLifecycleService:
    def __init__(self, items):
        self._items = items

    def list_items(self, state=None, limit=250):
        return {"status": "ok", "count": len(self._items), "items": self._items[:limit]}


def test_pricing_intelligence_governance_service_returns_governed_snapshot_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.pricing_intelligence_governance_service")
    service = module.PricingIntelligenceGovernanceService(runtime_dir=tmp_path / "runtime" / "staging" / "pricing-governance")
    service.lifecycle = _DummyLifecycleService(
        [
            {
                "rfq_id": "RFQ-PRC-004",
                "title": "Supply and delivery of office stationery",
                "description": "Framework agreement for stationery and consumables.",
                "unit_price": 118.0,
                "quantity": 20,
                "unit": "Each",
                "vat_rate": 0.15,
                "markup_rate": 0.25,
            }
        ]
    )

    latest = service.latest_pricing_intelligence()
    history = service.pricing_intelligence_history(limit=5)

    assert latest["status"] in {"ok", "watch"}
    assert latest["pricing_benchmark_readiness"]["ready"] is True
    assert latest["market_rate_comparison_readiness"]["ready"] is True
    assert latest["historical_pricing_reference_readiness"]["ready"] is True
    assert latest["supplier_quote_comparison_readiness"]["ready"] is True
    assert latest["margin_scenario_readiness"]["ready"] is True
    assert latest["pricing_confidence_score"] >= 0.0
    assert latest["mandatory_human_price_approval"] is True
    assert latest["autonomous_pricing_submission_enabled"] is False
    assert latest["live_procurement_commitment_enabled"] is False
    assert latest["live_supplier_ordering_enabled"] is False
    assert latest["production_tender_submission_enabled"] is False
    assert latest["dry_run_enforced"] is True
    assert latest["human_supervision_required"] is True
    assert latest["unresolved_pricing_blockers"] is not None
    assert history["count"] >= 1
