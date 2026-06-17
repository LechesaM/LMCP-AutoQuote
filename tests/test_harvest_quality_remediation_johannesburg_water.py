from __future__ import annotations

import json
from pathlib import Path

from app.services import live_rfq_store
from app.services.rfq_lifecycle_service import RfqLifecycleService


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "qualification_rfqs"


def test_johannesburg_water_electrical_components_rejects_for_missing_spec_detection(monkeypatch) -> None:
    fixture = json.loads((FIXTURES_DIR / "rfq_006_johannesburg_water_electrical_components.json").read_text(encoding="utf-8"))
    service = RfqLifecycleService()
    captured: dict[str, object] = {}

    class FakeStore:
        @staticmethod
        def list_items():
            return []

        @staticmethod
        def update_many(items, throughput_delta=None):
            captured["items"] = items
            captured["throughput_delta"] = throughput_delta
            return {"items": items, "throughput_delta": throughput_delta}

    def fake_promote(updates):
        captured["live_updates"] = updates
        return {"status": "ok", "count": len(updates), "items": updates}

    monkeypatch.setattr(service, "store", FakeStore())
    monkeypatch.setattr(
        live_rfq_store.LiveRFQStore,
        "get_all",
        staticmethod(lambda: {"status": "ok", "count": 1, "items": [fixture]}),
    )
    monkeypatch.setattr(live_rfq_store.LiveRFQStore, "promote", staticmethod(fake_promote))
    monkeypatch.setattr(service, "_live_store_index", lambda: {})
    monkeypatch.setattr(service, "_policy_check", lambda item: (True, []))
    monkeypatch.setattr(service, "_closing_date_status", lambda item: (True, "2026-06-19T12:00:00+00:00"))
    monkeypatch.setattr(service, "_document_confidence_score", lambda item: 0.95)
    monkeypatch.setattr(
        service,
        "_document_acquisition_step",
        lambda *args, **kwargs: {
            "downloaded_files": [
                {"status": "downloaded", "path": "/tmp/johannesburg_water_6000080537_electrical_components.pdf"}
            ],
            "report_path": "/tmp/johannesburg_water_6000080537_acquisition_report.json",
            "confidence": 0.95,
            "document_confidence_score": 0.95,
            "live_buyer_pack_path": "/tmp/johannesburg_water_6000080537_buyer_pack",
            "live_buyer_pack_manifest_path": "/tmp/johannesburg_water_6000080537_manifest.json",
        },
    )
    monkeypatch.setattr(
        service,
        "_document_parse_step",
        lambda *args, **kwargs: {
            "quote_safe": True,
            "text_extraction": [{"text_length": 84, "text": "Electrical components procurement opportunity."}],
            "document_intelligence": {
                "pricing_schedule_confidence": 0.91,
                "boq_confidence": 0.0,
                "extraction_confidence": 0.92,
                "has_sbd_forms": False,
                "returnables_mentioned": False,
                "reference_numbers": [],
                "delivery_mentioned": False,
                "supply_mentioned": False,
            },
            "report_path": "/tmp/johannesburg_water_6000080537_parse_report.json",
        },
    )
    monkeypatch.setattr(
        service,
        "_download_artifact_groups",
        lambda downloads: {
            "documents": [],
            "pricing_schedules": [],
            "boqs": [],
            "buyer_forms": [],
            "sbd_forms": [],
            "specifications": [],
        },
    )

    result = service.validate_visible_opportunities(limit=1, generate_local_pack=False)

    assert result["status"] == "ok"
    assert "items" in captured

    updated_item = captured["items"][0]
    live_update = captured["live_updates"][0]
    report_row = live_update["rfq_validation_report"]

    assert updated_item["primary_blocker"] == "rfq_spec_document_not_detected"
    assert updated_item["blocker_summary"] == "rfq_spec_document_not_detected (+1 more)"
    assert report_row["rfq_spec_document_detected"] is False
    assert report_row["sbd_or_returnables_detected"] is False
    assert report_row["document_verification_status"] == "verified"
    assert report_row["documents_downloaded_count"] == 1
    assert report_row["document_paths_count"] == 1
    assert report_row["blocked"] is True

    assert live_update["primary_blocker"] == "rfq_spec_document_not_detected"
    assert live_update["blocked"] is True
