from __future__ import annotations

import importlib


class _DummyLifecycleService:
    def __init__(self, items):
        self._items = items

    def list_items(self, state=None, limit=250):
        return {"status": "ok", "count": len(self._items), "items": self._items[:limit]}


def test_tender_classification_service_classifies_and_records_history(tmp_path) -> None:
    module = importlib.import_module("app.services.tender_classification_service")
    service = module.TenderClassificationService(runtime_dir=tmp_path / "runtime" / "staging" / "procurement-intelligence")
    service.lifecycle = _DummyLifecycleService(
        [
            {
                "rfq_id": "RFQ-10-001",
                "title": "Supply and delivery of office stationery",
                "description": "Framework agreement for stationery and consumables.",
                "buyer_name": "Sample Municipality",
                "category": "supplies",
                "submission_method": "portal",
                "closing_date": "2026-06-30T00:00:00+00:00",
            }
        ]
    )

    latest = service.latest_tender_classification()
    history = service.tender_classification_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["tender_classification_status"] == "ok"
    assert latest["latest_tender_classification"]["procurement_sector"] == "general" or latest["latest_tender_classification"]["procurement_sector"]
    assert latest["latest_tender_classification"]["tender_complexity"]["score"] >= 20.0
    assert latest["latest_tender_classification"]["mandatory_documents"]
    assert latest["latest_tender_classification"]["submission_urgency"]["label"] in {"normal", "standard", "elevated", "urgent", "critical"}
    assert history["count"] >= 1

