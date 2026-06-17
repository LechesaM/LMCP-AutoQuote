from __future__ import annotations

import os
from types import SimpleNamespace

from app.services import live_rfq_store
from app.services.rfq_lifecycle_service import RfqLifecycleService, _margin_percent


def test_validate_visible_opportunities_normalizes_rfq_id_before_writeback(monkeypatch) -> None:
    service = RfqLifecycleService()
    captured = {}

    class FakeStore:
        @staticmethod
        def list_items():
            return []

        @staticmethod
        def update_many(items, throughput_delta=None):
            captured["items"] = items
            captured["throughput_delta"] = throughput_delta
            return {"items": items, "throughput_delta": throughput_delta}

    monkeypatch.setattr(service, "store", FakeStore())
    monkeypatch.setattr(
        live_rfq_store.LiveRFQStore,
        "get_all",
        staticmethod(
            lambda: {
                "status": "ok",
                "count": 1,
                "items": [
                    {
                        "buyer_rfq_number": "RFQ-123",
                        "title": "RFQ-123",
                        "buyer_name": "Metro Procurement Unit",
                        "source": "submission_packages",
                        "source_url": "https://example.org/rfq/RFQ-123",
                        "detail_url": "https://example.org/rfq/RFQ-123/detail",
                        "document_url": "https://example.org/rfq/RFQ-123/document.pdf",
                        "document_paths": ["/tmp/rfq-123-document.pdf"],
                        "line_items": [{"description": "Office consumables", "quantity": 1, "unit_price": 100.0}],
                    }
                ],
            }
        ),
    )
    monkeypatch.setattr(service, "_live_store_index", lambda: {})
    monkeypatch.setattr(service, "_policy_check", lambda item: (False, ["test_block"]))
    monkeypatch.setattr(service, "_enrich_lifecycle_item", lambda item, live_index: item)
    monkeypatch.setattr(service, "_closing_date_status", lambda item: (True, "2026-07-01T12:00:00+00:00"))
    monkeypatch.setattr(service, "_document_confidence_score", lambda item: 1.0)
    monkeypatch.setattr(
        service,
        "_document_acquisition_step",
        lambda *args, **kwargs: {"downloaded_files": [], "report_path": "", "confidence": 0.0, "document_confidence_score": 0.0},
    )
    monkeypatch.setattr(
        service,
        "_document_parse_step",
        lambda *args, **kwargs: {
            "quote_safe": True,
            "text_extraction": [{"text_length": 10}],
            "document_intelligence": {
                "pricing_schedule_confidence": 0.9,
                "boq_confidence": 0.9,
                "extraction_confidence": 0.9,
                "has_sbd_forms": True,
                "returnables_mentioned": True,
                "reference_numbers": ["RFQ-123"],
                "delivery_mentioned": True,
                "supply_mentioned": True,
            },
            "report_path": "/tmp/rfq-123-report.json",
        },
    )

    result = service.validate_visible_opportunities(limit=1, generate_local_pack=False)

    assert result["status"] == "ok"
    assert captured["items"]
    assert captured["items"][0]["rfq_id"] == "RFQ-123"
    assert captured["items"][0]["rfq_reference"] == "RFQ-123"
    assert captured["items"][0]["primary_blocker"] == "test_block"
    assert captured["items"][0]["blocker_summary"].startswith("test_block")


def test_price_step_uses_workspace_runtime_dir(monkeypatch) -> None:
    service = RfqLifecycleService()
    captured = {}

    def fake_enrich(payload, runtime_dir=None):
        captured["runtime_dir"] = runtime_dir
        captured["project_root"] = os.getenv("LMCP_PROJECT_ROOT")
        captured["runtime_env"] = os.getenv("LMCP_RUNTIME_DIR")
        return {
            "status": "ok",
            "priced": True,
            "estimated_profit": 48500.0,
            "estimated_margin_percent": 41.0,
            "payload": payload,
        }

    monkeypatch.setattr(
        "app.services.real_profit_pricing_service.enrich_with_real_profit_pricing",
        fake_enrich,
    )

    result = service._price_step(
        {
            "buyer_rfq_number": "REAL-PILOT-001",
            "title": "Supply and Delivery of Office Consumables",
            "estimated_profit": 48500.0,
            "estimated_margin_percent": 41.0,
        }
    )

    assert result["status"] == "ok"
    assert result["priced"] is True
    assert captured["runtime_dir"] == "/Users/cash/Documents/runtime"
    assert captured["project_root"] == "/Users/cash/Documents"
    assert captured["runtime_env"] == "/Users/cash/Documents/runtime"


def test_margin_percent_reads_estimated_margin_percent() -> None:
    assert _margin_percent({"estimated_margin_percent": 41.0}) == 41.0
