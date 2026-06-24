from __future__ import annotations

import importlib


class _DummyLifecycleService:
    def __init__(self, items):
        self._items = items

    def list_items(self, state=None, limit=250):
        return {"status": "ok", "count": len(self._items), "items": self._items[:limit]}


def test_supplier_fit_scoring_scores_supplier_match_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.supplier_fit_scoring_service")
    service = module.SupplierFitScoringService(runtime_dir=tmp_path / "runtime" / "staging" / "supplier-intelligence")
    service.lifecycle = _DummyLifecycleService(
        [
            {
                "rfq_id": "RFQ-SUP-001",
                "title": "Supply and delivery of office stationery",
                "description": "Framework agreement for stationery and consumables.",
                "buyer_name": "Sample Municipality",
                "category": "supplies",
                "province": "Gauteng",
                "delivery_location": "Gauteng",
            }
        ]
    )
    supplier = {
        "supplier_id": "SUP-002",
        "supplier_name": "National Office & Hygiene Distributors",
        "province": "Gauteng",
        "city": "Johannesburg",
        "contact_person": "Bid Desk",
        "email": "bids@example.com",
        "phone": "+27-11-000-0001",
        "delivery_regions": ["All"],
        "products": [{"product_name": "A4 paper", "category": "stationery_office", "unit_price": 72.0, "available_stock": 30000}],
    }

    latest = service.score_supplier_fit(supplier)
    history = service.supplier_fit_scoring_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["supplier_fit_score"] >= 55.0
    assert latest["latest_supplier_fit_scoring"]["recommended_supplier_tier"] in {"A", "B", "C", "D"}
    assert latest["latest_supplier_fit_scoring"]["geographic_suitability"] >= 60.0
    assert latest["latest_supplier_fit_scoring"]["capacity_suitability"] >= 20.0
    assert history["count"] >= 1

