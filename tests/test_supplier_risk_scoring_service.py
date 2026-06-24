from __future__ import annotations

import importlib


class _DummyLifecycleService:
    def __init__(self, items):
        self._items = items

    def list_items(self, state=None, limit=250):
        return {"status": "ok", "count": len(self._items), "items": self._items[:limit]}


def test_supplier_risk_scoring_detects_delivery_risk_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.supplier_risk_scoring_service")
    service = module.SupplierRiskScoringService(runtime_dir=tmp_path / "runtime" / "staging" / "supplier-intelligence")
    service.lifecycle = _DummyLifecycleService(
        [
            {
                "rfq_id": "RFQ-SUP-002",
                "title": "Urgent supply contract",
                "description": "Immediate stationery delivery required.",
                "province": "Western Cape",
                "delivery_location": "Western Cape",
            }
        ]
    )
    supplier = {
        "supplier_id": "SUP-004",
        "supplier_name": "Agri Water and Safety Wholesale",
        "province": "Western Cape",
        "city": "Cape Town",
        "contact_person": "Public Sector Sales",
        "email": "tenders@example.com",
        "phone": "+27-21-000-0004",
        "delivery_regions": ["All"],
        "products": [{"product_name": "Road sign", "category": "safety_security_general", "unit_price": 1450.0, "available_stock": 3000, "lead_time_days": 5}],
    }

    latest = service.score_supplier_risk(supplier)
    history = service.supplier_risk_scoring_history(limit=5)

    assert latest["status"] in {"ok", "watch", "blocked"}
    assert latest["supplier_risk_score"] >= 0.0
    assert latest["latest_supplier_risk_scoring"]["delivery_risk_score"] >= 0.0
    assert latest["latest_supplier_risk_scoring"]["supplier_risk_flags"]
    assert history["count"] >= 1

