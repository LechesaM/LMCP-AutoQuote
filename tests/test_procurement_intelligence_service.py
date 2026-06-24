from __future__ import annotations

import importlib


class _DummyLifecycleService:
    def __init__(self, items):
        self._items = items

    def list_items(self, state=None, limit=250):
        return {"status": "ok", "count": len(self._items), "items": self._items[:limit]}


def test_procurement_intelligence_service_aggregates_scores_and_heatmap(tmp_path) -> None:
    module = importlib.import_module("app.services.procurement_intelligence_service")
    service = module.ProcurementIntelligenceService(runtime_dir=tmp_path / "runtime" / "staging" / "procurement-intelligence")
    service.lifecycle = _DummyLifecycleService(
        [
            {
                "rfq_id": "RFQ-10-004",
                "title": "Supply and delivery of office stationery",
                "description": "Framework agreement for stationery and consumables.",
                "buyer_name": "Sample Municipality",
                "category": "supplies",
                "submission_method": "portal",
                "closing_date": "2026-06-30T00:00:00+00:00",
            },
            {
                "rfq_id": "RFQ-10-005",
                "title": "IT hardware and network equipment",
                "description": "Supply of routers, switches and laptops for regional offices.",
                "buyer_name": "Sample Municipality",
                "category": "information_technology",
                "submission_method": "portal",
                "closing_date": "2026-06-27T00:00:00+00:00",
            },
        ]
    )

    latest = service.latest_procurement_intelligence()
    history = service.procurement_intelligence_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["procurement_intelligence_score"] >= 0.0
    assert latest["latest_procurement_intelligence"]["opportunity_score"] >= 0.0
    assert latest["latest_procurement_intelligence"]["procurement_category_heatmap"]["summary"]["total_tenders"] >= 1
    assert latest["risk_flags"] is not None
    assert latest["mandatory_documents"]
    assert latest["supplier_fit_scoring"]["supplier_fit_score"] >= 0.0
    assert history["count"] >= 1

