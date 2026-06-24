from __future__ import annotations

import importlib


class _DummyLifecycleService:
    def __init__(self, items):
        self._items = items

    def list_items(self, state=None, limit=250):
        return {"status": "ok", "count": len(self._items), "items": self._items[:limit]}


def test_supplier_intelligence_service_scores_best_supplier_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.supplier_intelligence_service")
    service = module.SupplierIntelligenceService(runtime_dir=tmp_path / "runtime" / "staging" / "supplier-intelligence")
    service.lifecycle = _DummyLifecycleService(
        [
            {
                "rfq_id": "RFQ-SUP-003",
                "title": "Supply and delivery of office stationery",
                "description": "Framework agreement for stationery and consumables.",
                "buyer_name": "Sample Municipality",
                "category": "supplies",
                "province": "Gauteng",
                "delivery_location": "Gauteng",
                "closing_date": "2026-06-30T00:00:00+00:00",
            }
        ]
    )
    service._supplier_records = lambda: [
        {
            "supplier_id": "SUP-002",
            "supplier_name": "National Office & Hygiene Distributors",
            "province": "Gauteng",
            "city": "Johannesburg",
            "contact_person": "Bid Desk",
            "email": "bids@example.com",
            "phone": "+27-11-000-0001",
            "delivery_regions": ["All"],
            "products": [{"product_name": "A4 paper", "category": "stationery_office", "unit_price": 72.0, "available_stock": 30000, "lead_time_days": 2}],
        },
        {
            "supplier_id": "SUP-004",
            "supplier_name": "Agri Water and Safety Wholesale",
            "province": "Western Cape",
            "city": "Cape Town",
            "contact_person": "Public Sector Sales",
            "email": "tenders@example.com",
            "phone": "+27-21-000-0004",
            "delivery_regions": ["All"],
            "products": [{"product_name": "Road sign", "category": "safety_security_general", "unit_price": 1450.0, "available_stock": 3000, "lead_time_days": 5}],
        },
    ]

    latest = service.latest_supplier_intelligence()
    history = service.supplier_intelligence_history(limit=5)

    assert latest["status"] in {"ok", "watch"}
    assert latest["supplier_intelligence_score"] >= 0.0
    assert latest["latest_supplier_intelligence"]["supplier_fit_score"] >= 0.0
    assert latest["latest_supplier_intelligence"]["recommended_supplier_tier"] in {"A", "B", "C", "D"}
    assert latest["supplier_rankings"]
    assert latest["supplier_category_heatmap"]["summary"]["total_suppliers"] >= 1
    assert latest["unresolved_supplier_blockers"] is not None
    assert history["count"] >= 1

