import json

from app.services import live_rfq_store
from app.services import rfq_lifecycle_service
from app.services.rfq_lifecycle_service import RfqLifecycleService
from app.services.rfq_state_store import RfqStateStore


def test_active_rfq_without_supplier_quotes_can_access_provisional_pricing(tmp_path, monkeypatch):
    store = tmp_path / "live_rfqs.json"
    store.write_text(
        json.dumps(
            {
                "status": "ok",
                "items": [
                    {
                        "rfq_number": "ACTIVE-PRICING",
                        "title": "Supply and delivery of valves",
                        "buyer_name": "Buyer",
                        "closing_date": "2026-08-01T12:00:00+02:00",
                        "status": "Published",
                        "supplier_quotes": [],
                        "line_items": [{"description": "Valve", "quantity": 1, "unit": "each"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(live_rfq_store, "LIVE_RFQ_STORE_PATH", store)
    monkeypatch.setattr(rfq_lifecycle_service, "MANUAL_PRICING_DIR", tmp_path / "manual_pricing")

    service = RfqLifecycleService(RfqStateStore(tmp_path / "rfq_lifecycle" / "rfqs.json"))
    response = service.get_manual_pricing("ACTIVE-PRICING")

    assert response["status"] == "ok"
    assert response["saved"] is False


def test_historical_rfq_is_excluded_from_active_pricing_queue(tmp_path, monkeypatch):
    store = tmp_path / "live_rfqs.json"
    store.write_text(
        json.dumps(
            {
                "status": "ok",
                "items": [
                    {
                        "rfq_number": "OLD-PRICING",
                        "title": "Supply and delivery of old valves",
                        "buyer_name": "Buyer",
                        "closing_date": "2026-01-01",
                        "status": "Published",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(live_rfq_store, "LIVE_RFQ_STORE_PATH", store)

    assert live_rfq_store.list_active_rfqs()["count"] == 0
    assert live_rfq_store.list_historical_rfqs()["count"] == 1
