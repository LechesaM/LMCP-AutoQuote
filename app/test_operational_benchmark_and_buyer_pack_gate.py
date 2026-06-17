from __future__ import annotations

from pathlib import Path

from app.services.external_submission_benchmark_service import (
    BENCHMARK_CHECKLIST,
    benchmark_required_keys,
    build_external_submission_benchmark_template,
    is_external_submission_benchmark_complete,
)
from app.services.rfq_lifecycle_service import RfqLifecycleService, _buyer_pack_downloaded_from_payload
from app.services.tender_harvester import _lmcp_apply_quantity_safety_gate, _lmcp_buyer_pack_downloaded


def test_benchmark_template_exposes_five_required_criteria():
    template = build_external_submission_benchmark_template("RFQ-1", "Lesedi", "Buyer A")

    assert template["benchmark_name"] == "First Externally Verified Submission"
    assert benchmark_required_keys() == [row["key"] for row in BENCHMARK_CHECKLIST]
    assert template["criteria"] == {row["key"]: False for row in BENCHMARK_CHECKLIST}
    assert is_external_submission_benchmark_complete(template["criteria"]) is False
    assert len(template["required_evidence"]) == 5


def test_buyer_pack_detection_prefers_explicit_or_existing_evidence(tmp_path: Path):
    pack_file = tmp_path / "buyer-pack.pdf"
    pack_file.write_bytes(b"%PDF-1.7")

    explicit = {"buyer_pack_downloaded": True}
    path_based = {"document_acquisition_status": "verified", "buyer_pack_path": str(pack_file)}
    missing = {"document_acquisition_status": "document_acquisition_pending"}

    assert _lmcp_buyer_pack_downloaded(explicit) is True
    assert _lmcp_buyer_pack_downloaded(path_based) is True
    assert _lmcp_buyer_pack_downloaded(missing) is False
    assert _buyer_pack_downloaded_from_payload(explicit) is True
    assert _buyer_pack_downloaded_from_payload(path_based) is True
    assert _buyer_pack_downloaded_from_payload(missing) is False


def test_quantity_gate_blocks_at_document_acquisition_until_buyer_pack_exists():
    item = {
        "eligible": True,
        "buyer_pack_downloaded": False,
        "buyer_pack_verified": False,
        "document_acquisition_status": "document_acquisition_pending",
        "requires_quantity_verification": False,
        "quote_ready": True,
        "auto_quote_enabled": True,
        "auto_submit": True,
        "auto_submission_gate_allowed": True,
        "pipeline_status": "eligible_for_quote_pack",
    }

    gated = _lmcp_apply_quantity_safety_gate(item)

    assert gated["buyer_pack_downloaded"] is False
    assert gated["pipeline_status"] == "document_acquisition_pending"
    assert gated["quantity_safety_status"] == "document_acquisition_pending"
    assert gated["auto_submission_gate_reason"] == "buyer_pack_download_required"
    assert gated["quote_ready"] is False


def test_lifecycle_service_normalizes_missing_buyer_pack_as_document_acquisition_pending():
    service = RfqLifecycleService()
    normalized = service._normalize_item(
        {
            "title": "Supply and delivery of office consumables",
            "buyer_name": "Msukaligwa",
            "eligible": True,
            "qualified": True,
            "estimated_profit": 50000,
            "estimated_margin": 30,
            "document_acquisition_status": "document_acquisition_pending",
        }
    )

    assert normalized["buyer_pack_downloaded"] is False
    assert normalized["current_state"] == "DOCUMENT_ACQUISITION_PENDING"
    assert normalized["document_acquisition_status"] == "document_acquisition_pending"
