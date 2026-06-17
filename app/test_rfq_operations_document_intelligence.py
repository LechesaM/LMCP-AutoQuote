from __future__ import annotations

import json
from pathlib import Path

from app.api.operator_workflow_contracts import get_operator_workflow_detail, get_operator_workflow_rows
from app.services import live_rfq_store
from app.services.rfq_lifecycle_service import RfqLifecycleService
from app.services.live_rfq_store import summarize_rfq_document_intelligence, upsert_live_rfq


def _write_live_store(path: Path, items: list[dict]) -> None:
    path.write_text(
        json.dumps({"status": "ok", "updated_at": "2026-06-13T00:00:00Z", "count": len(items), "items": items}, indent=2),
        encoding="utf-8",
    )


def test_acquisition_state_persistence_on_upsert(tmp_path: Path, monkeypatch) -> None:
    store_path = tmp_path / "live_rfqs.json"
    monkeypatch.setattr(live_rfq_store, "LIVE_RFQ_STORE_PATH", store_path)
    quote_pack_dir = tmp_path / "quote-pack"
    quote_pack_dir.mkdir()
    (quote_pack_dir / "formal_quotation_v44.html").write_text("<html>quote</html>", encoding="utf-8")

    payload = {
        "buyer_rfq_number": "RFQ-OPS-001",
        "title": "Supply and delivery of office consumables",
        "buyer_name": "Buyer A",
        "closing_date": "2026-07-01",
        "estimated_profit": 55000,
        "briefing_required": False,
        "document_acquisition_status": "buyer_pack_verified",
        "buyer_pack_downloaded": True,
        "buyer_pack_download_timestamp": "2026-06-13T08:00:00Z",
        "buyer_pack_source": "https://example.com/buyer-pack",
        "document_acquisition_result": {
            "live_buyer_pack_path": "/tmp/buyer-pack",
            "main_document_path": "/tmp/buyer-pack/main.docx",
        },
        "boq_detected": True,
        "pricing_schedule_detected": True,
        "returnables_detected": True,
        "quote_pack_generated": True,
        "quote_pack_path": str(quote_pack_dir),
    }

    result = upsert_live_rfq(payload)
    stored = json.loads(store_path.read_text(encoding="utf-8"))
    item = stored["items"][0]

    assert result["count"] == 1
    assert item["rfq_discovered"] is True
    assert item["buyer_pack_downloaded"] is True
    assert item["buyer_pack_status"] == "downloaded"
    assert item["boq_status"] == "detected"
    assert item["pricing_schedule_status"] == "detected"
    assert item["returnables_status"] == "detected"
    assert item["quote_pack_status"] == "generated"
    assert item["acquisition_readiness_score"] == 100
    assert item["quote_pack_readiness_score"] == 100


def test_readiness_score_and_extraction_failure_classification() -> None:
    summary = summarize_rfq_document_intelligence(
        {
            "rfq_discovered": True,
            "buyer_pack_downloaded": True,
            "buyer_pack_verified": True,
            "buyer_pack_download_timestamp": "2026-06-13T08:00:00Z",
            "document_intelligence_report_path": "/tmp/report.json",
            "document_acquisition_status": "buyer_pack_verified",
        }
    )

    assert summary["quote_pack_readiness_score"] == 20
    assert summary["buyer_pack_status"] == "downloaded"
    assert summary["boq_status"] == "failed"
    assert summary["pricing_schedule_status"] == "failed"
    assert summary["returnables_status"] == "failed"
    assert summary["extraction_failure_reason"] == "boq_not_detected;pricing_schedule_not_detected;returnables_not_detected"


def test_operations_api_response_shape_includes_acquisition_and_extraction_state(tmp_path: Path, monkeypatch) -> None:
    store_path = tmp_path / "live_rfqs.json"
    monkeypatch.setattr(live_rfq_store, "LIVE_RFQ_STORE_PATH", store_path)

    _write_live_store(
        store_path,
        [
            {
                "rfq_id": "RFQ-OPS-002",
                "buyer_rfq_number": "RFQ-OPS-002",
                "title": "Supply and delivery of stationery",
                "buyer_name": "Buyer B",
                "province": "GP",
                "closing_date": "2026-07-01",
                "estimated_profit": 48000,
                "briefing_required": False,
                "document_acquisition_status": "buyer_pack_verified",
                "buyer_pack_downloaded": True,
                "buyer_pack_download_timestamp": "2026-06-13T09:00:00Z",
                "buyer_pack_source": "https://example.com/buyer-pack",
                "document_acquisition_result": {
                    "live_buyer_pack_path": "/tmp/pack",
                    "main_document_path": "/tmp/pack/main.docx",
                },
                "boq_detected": True,
                "pricing_schedule_detected": True,
                "returnables_detected": False,
                "quote_pack_generated": False,
            }
        ],
    )

    rows = get_operator_workflow_rows(limit=5)
    detail = get_operator_workflow_detail("RFQ-OPS-002")
    row = rows["rows"][0]

    assert rows["status"] == "ok"
    assert rows["count"] == 1
    assert "funnel_metrics" in rows
    assert rows["funnel_metrics"]["discovered_count"] >= 1
    assert row["buyer_pack_status"] == "downloaded"
    assert row["boq_status"] == "detected"
    assert row["pricing_schedule_status"] == "detected"
    assert row["returnables_status"] in {"failed", "not_attempted"}
    assert "acquisition_readiness_score" in row
    assert row["lifecycle_stage_label"] in {"PRICING DETECTED", "RETURNABLES DETECTED", "QUOTE PACK GENERATED"}
    assert detail["document_intelligence"]["buyer_pack_status"] == "downloaded"
    assert detail["acquisition_readiness_score"] == 60
    assert detail["lifecycle_stage"] in {"PRICING DETECTED", "RETURNABLES DETECTED", "QUOTE PACK GENERATED"}


def test_lifecycle_state_hard_gate_stays_at_highest_completed_stage(tmp_path: Path) -> None:
    service = RfqLifecycleService()
    quote_pack_dir = tmp_path / "quote-pack"
    quote_pack_dir.mkdir()
    (quote_pack_dir / "buyer_pricing_schedule_v44.csv").write_text("item_no,description\n1,Service", encoding="utf-8")
    blocked_payload = {
        "current_state": "QUOTE_PACK_READY",
        "buyer_pack_downloaded": True,
        "boq_detected": False,
        "pricing_schedule_detected": False,
        "returnables_detected": False,
        "quote_pack_generated": False,
        "submission_status": "not_submitted",
    }
    blocked_summary = summarize_rfq_document_intelligence(blocked_payload)
    assert blocked_summary["quote_ready_allowed"] is False
    assert service._resolve_lifecycle_state(blocked_payload, blocked_summary, "QUOTE_PACK_READY") == "BUYER_PACK_VERIFIED"

    ready_payload = {
        "current_state": "PRICED",
        "buyer_pack_downloaded": True,
        "boq_detected": True,
        "pricing_schedule_detected": True,
        "returnables_detected": True,
        "quote_pack_generated": True,
        "quote_pack_path": str(quote_pack_dir),
        "submission_status": "not_submitted",
    }
    ready_summary = summarize_rfq_document_intelligence(ready_payload)
    assert ready_summary["quote_ready_allowed"] is True
    assert service._resolve_lifecycle_state(ready_payload, ready_summary, "PRICED") == "QUOTE_PACK_READY"
