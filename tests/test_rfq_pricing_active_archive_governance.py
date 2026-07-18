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


def test_extracted_rows_load_as_manual_pricing_workspace_without_supplier_quotes(tmp_path, monkeypatch):
    store = tmp_path / "live_rfqs.json"
    store.write_text(
        json.dumps(
            {
                "status": "ok",
                "items": [
                    {
                        "rfq_number": "6000080601",
                        "reference_number": "6000080601",
                        "title": "Supply and deliver materials as per attached RFQ.",
                        "buyer_name": "Johannesburg Water",
                        "closing_date": "2026-08-01T12:00:00+02:00",
                        "status": "Published",
                        "supplier_quotes": [],
                        "line_items": [
                            {
                                "item_number": "5897",
                                "material_number": "5897",
                                "description": "PENETRATING OIL SPRAY 400ML",
                                "quantity": 300,
                                "unit": "EA",
                                "supplier_rate": None,
                                "selling_rate": None,
                                "source_page": 1,
                            },
                            {
                                "item_number": "1846",
                                "description": "GENERAL PURPOSE E6013 WELDING ELECTRODES",
                                "quantity": 500,
                                "unit": "EA",
                                "source_page": 1,
                            },
                        ],
                        "mandatory_returnables": [{"name": "Company letterhead"}],
                        "missing_returnables": [{"name": "Company letterhead"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(live_rfq_store, "LIVE_RFQ_STORE_PATH", store)
    monkeypatch.setattr(rfq_lifecycle_service, "MANUAL_PRICING_DIR", tmp_path / "manual_pricing")

    lifecycle_store = tmp_path / "rfq_lifecycle" / "rfqs.json"
    service = RfqLifecycleService(RfqStateStore(lifecycle_store))
    response = service.get_manual_pricing("6000080601")

    assert response["status"] == "ok"
    assert response["saved"] is False
    assert response["source_pricing_row_count"] == 2
    assert response["supplier_quotes_required_for_pricing"] is False
    assert response["line_items"][0]["item_number"] == "5897"
    assert response["line_items"][0]["quantity"] == 300
    assert response["pricing_policy"]["minimum_markup_percent"] == 25.0
    assert response["pricing_policy"]["minimum_projected_net_profit"] == 25000.0
    assert response["pricing_policy"]["scenario_35"]["recommended_markup_scenario"] == 35.0
    assert service.store.list_items() == []


def test_manual_pricing_save_is_idempotent_preserves_overrides_and_does_not_mutate_live_or_lifecycle(tmp_path, monkeypatch):
    store = tmp_path / "live_rfqs.json"
    original_payload = {
        "status": "ok",
        "items": [
            {
                "rfq_number": "6000080601",
                "reference_number": "6000080601",
                "title": "Supply and deliver materials as per attached RFQ.",
                "buyer_name": "Johannesburg Water",
                "closing_date": "2026-08-01T12:00:00+02:00",
                "status": "Published",
                "line_items": [
                    {
                        "item_number": "5897",
                        "description": "PENETRATING OIL SPRAY 400ML",
                        "quantity": 300,
                        "unit": "EA",
                        "source_page": 1,
                    },
                    {
                        "item_number": "1846",
                        "description": "WELDING ELECTRODES",
                        "quantity": 500,
                        "unit": "EA",
                        "source_page": 1,
                    },
                ],
                "missing_returnables": [{"name": "Company letterhead"}],
                "submission_pack_status": "blocked_pending_returnables_review",
            },
            {
                "rfq_number": "UNRELATED",
                "title": "Other active supply RFQ",
                "closing_date": "2026-08-01T12:00:00+02:00",
                "status": "Published",
            },
        ],
    }
    store.write_text(json.dumps(original_payload, indent=2), encoding="utf-8")
    before_live = store.read_text(encoding="utf-8")
    monkeypatch.setattr(live_rfq_store, "LIVE_RFQ_STORE_PATH", store)
    monkeypatch.setattr(rfq_lifecycle_service, "MANUAL_PRICING_DIR", tmp_path / "manual_pricing")

    lifecycle_store = tmp_path / "rfq_lifecycle" / "rfqs.json"
    service = RfqLifecycleService(RfqStateStore(lifecycle_store))
    payload = {
        "line_items": [
            {
                "item_number": "5897",
                "description": "PENETRATING OIL SPRAY 400ML",
                "quantity": 300,
                "unit": "EA",
                "supplier_rate": 10,
                "markup_percent": 25,
                "pricing_source": "operator_provisional_estimate",
            },
            {
                "item_number": "1846",
                "description": "WELDING ELECTRODES",
                "quantity": 500,
                "unit": "EA",
                "unit_cost": 20,
                "selling_rate": 30,
                "manual_override": True,
                "pricing_source": "operator_provisional_estimate",
            },
        ],
        "vat_rate": 15,
    }

    first = service.save_manual_pricing("6000080601", payload)
    second = service.save_manual_pricing("6000080601", payload)
    saved = json.loads((tmp_path / "manual_pricing" / "6000080601.json").read_text(encoding="utf-8"))

    assert first["status"] == "needs_review"
    assert second["status"] == "needs_review"
    assert len(saved["line_items"]) == 2
    assert saved["line_items"][0]["supplier_rate"] == 10
    assert saved["line_items"][0]["selling_rate"] == 12.5
    assert saved["line_items"][1]["manual_override"] is True
    assert saved["line_items"][1]["selling_rate"] == 30
    assert saved["totals"]["minimum_profit_required"] == 25000.0
    assert saved["totals"]["supplier_validation_required"] is True
    assert saved["totals"]["quote_pack_generated"] is False
    assert saved["totals"]["submission_pack_generated"] is False
    assert saved["safety"]["live_rfq_store_modified"] is False
    assert saved["safety"]["lifecycle_store_modified"] is False
    assert store.read_text(encoding="utf-8") == before_live
    assert service.store.list_items() == []


def test_manual_pricing_validation_handles_blank_cost_zero_and_decimal_quantities(tmp_path, monkeypatch):
    monkeypatch.setattr(rfq_lifecycle_service, "MANUAL_PRICING_DIR", tmp_path / "manual_pricing")
    service = RfqLifecycleService(RfqStateStore(tmp_path / "rfq_lifecycle" / "rfqs.json"))

    line_items, totals, blockers = service._manual_pricing_validation(
        {
            "line_items": [
                {"description": "Blank cost", "quantity": 2.5, "unit": "L", "unit_cost": "", "selling_price": ""},
                {"description": "Zero quantity", "quantity": 0, "unit": "EA", "unit_cost": 10, "markup_percent": 25},
            ],
            "vat_rate": 15,
        }
    )

    assert line_items[0]["quantity"] == 2.5
    assert "line_1_invalid_selling_price" in blockers
    assert "line_2_invalid_quantity" in blockers
    assert totals["verified"] is False
