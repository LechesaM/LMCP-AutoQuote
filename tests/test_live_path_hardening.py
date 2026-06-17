from __future__ import annotations

import json
from pathlib import Path

from app.services import tender_harvester
from app.services.live_rfq_store import promote_live_rfqs, save_live_rfqs


SMOKE_SOURCE_FILE = Path(__file__).resolve().parents[1] / "app" / "data" / "smoke_harvest_sources.json"


def test_live_harvest_uses_injected_browser_and_health_snapshot(tmp_path: Path) -> None:
    source_health_snapshot = {
        "Smoke Fixture eTenders": {
            "failure_count": 0,
            "candidate_total": 7,
            "qualified_candidate_total": 2,
            "document_candidate_total": 1,
            "last_success_at": "2026-06-02T20:00:00+00:00",
            "consecutive_empty_runs": 0,
        }
    }

    result = tender_harvester.run_national_tender_radar(
        max_total=2,
        max_per_source=1,
        max_sources_per_cycle=1,
        source_file=str(SMOKE_SOURCE_FILE),
        controlled_mode=False,
        persist_to_live_store=False,
        browser_available=False,
        source_health_snapshot=source_health_snapshot,
        source_timeout_seconds=3,
        playwright_timeout_ms=5000,
    )

    assert result["status"] == "ok"
    assert result["browser_available"] is False
    assert result["source_health_snapshot_injected"] is True
    assert result["source_health_overview"]["source_count"] == 1
    assert result["source_health_overview"]["top_sources"][0]["candidate_total"] == 7
    assert result["source_runs"][0]["browser_available"] is False


def test_live_navigation_gate_accepts_injected_resolver_outputs() -> None:
    item = {
        "eligible": True,
        "quote_ready": False,
        "source_name": "Smoke Fixture eTenders",
        "source_url": "file:///Users/cash/Documents/app/data/fixtures/smoke_etenders_fixture.html",
        "title": "Example live RFQ",
        "description": "Example live RFQ",
        "buyer_rfq_number": "RFQ-123",
        "rfq_number": "RFQ-123",
        "reference_number": "RFQ-123",
    }
    resolver_overrides = {
        "v50_8_true_detail": {
            "status": "ok",
            "safe_to_follow_detail": True,
            "safe_to_download": True,
            "recommended_action": "promote_verified_detail_page",
            "recommended_detail_links": [{"url": "https://example.com/detail"}],
            "recommended_document_links": [{"url": "https://example.com/document.pdf"}],
            "verified_detail_count": 1,
            "verified_document_count": 1,
            "matched_row_count": 1,
            "candidate_url_count": 1,
        }
    }

    result = tender_harvester._lmcp_apply_v50_7_etenders_navigation_gate(item, resolver_overrides=resolver_overrides)

    assert result["v50_8_extended_resolution_status"] == "verified_document"
    assert result["document_url"] == "https://example.com/document.pdf"
    assert result["detail_url"] == "https://example.com/document.pdf"
    assert result["v50_7_navigation_status"] == "verified_document"


def test_live_navigation_gate_discovers_tender_id_from_reconstruction() -> None:
    item = {
        "eligible": True,
        "quote_ready": False,
        "source_name": "National Treasury eTenders",
        "source_url": "https://www.etenders.gov.za/Home/opportunities",
        "document_url": "https://www.etenders.gov.za/Home/opportunities",
        "title": "SUPPLY AND DELIVERY OF JOINTS ON AN AS AND WHEN REQUIRED BASIS FOR A PERIOD OF 5 YEARS AT LETHABO POWER STATION 10/06/2026 in 37 days",
        "description": "SUPPLY AND DELIVERY OF JOINTS ON AN AS AND WHEN REQUIRED BASIS FOR A PERIOD OF 5 YEARS AT LETHABO POWER STATION 10/06/2026 in 37 days",
        "buyer_rfq_number": "SUPPLY AND DELIVERY OF JOINTS ON AN AS AND WHEN REQUIRED BASIS FOR A PERIOD OF 5 YEARS AT LETHABO POWER STATION 10/06/2026 in 37 days",
        "rfq_number": "SUPPLY AND DELIVERY OF JOINTS ON AN AS AND WHEN REQUIRED BASIS FOR A PERIOD OF 5 YEARS AT LETHABO POWER STATION 10/06/2026 in 37 days",
        "reference_number": "SUPPLY AND DELIVERY OF JOINTS ON AN AS AND WHEN REQUIRED BASIS FOR A PERIOD OF 5 YEARS AT LETHABO POWER STATION 10/06/2026 in 37 days",
    }
    resolver_overrides = {
        "v50_8_true_detail": {
            "status": "ok",
            "recommended_action": "no_matching_row",
            "safe_to_follow_detail": False,
            "safe_to_download": False,
            "matched_row_count": 0,
        },
        "v50_8_1_ajax": {
            "status": "ok",
            "recommended_action": "matched_ajax_row_but_no_verified_document",
            "safe_to_follow_detail": False,
            "safe_to_download": False,
            "matched_row_count": 1,
            "matched_rows": [{"text_preview": "row without direct URL"}],
        },
        "v50_8_2_reconstruction": {
            "status": "ok",
            "recommended_action": "candidate_urls_reconstructed_but_not_verified",
            "safe_to_follow_detail": False,
            "safe_to_download": False,
            "matched_row_count": 1,
            "candidate_url_count": 2,
            "reconstructed_rows": [
                {
                    "match_score": 0.82,
                    "fields": {"ids": ["155559"]},
                }
            ],
        },
        "v50_9_1_tenderdetails_inspect": {
            "status": "ok",
            "details_ok": True,
            "safe_to_download": True,
            "document_count": 1,
            "recommended_document_links": [
                {"url": "https://www.etenders.gov.za/Home/DownloadSpec?documentId=155559&source=sharepoint"}
            ],
            "documents": [{"filename": "Lethabo Joints.zip"}],
        },
    }

    result = tender_harvester._lmcp_apply_v50_7_etenders_navigation_gate(item, resolver_overrides=resolver_overrides)

    assert result["v50_8_discovered_tender_id"] == "155559"
    assert result["v50_8_extended_resolution_status"] == "verified_document"
    assert result["document_url"] == "https://www.etenders.gov.za/Home/DownloadSpec?documentId=155559&source=sharepoint"
    assert "v50_8_2_reconstruction_result" in result
    assert "v50_9_1_tenderdetails_inspect_result" in result


def test_live_navigation_gate_preserves_quote_ready_after_quantity_verification() -> None:
    item = {
        "eligible": True,
        "quote_ready": True,
        "requires_quantity_verification": True,
        "pipeline_status": "quantity_verification_required",
        "source_name": "Smoke Fixture eTenders",
        "source_url": "file:///Users/cash/Documents/app/data/fixtures/smoke_etenders_fixture.html",
        "title": "Example live RFQ",
        "description": "Example live RFQ",
        "buyer_rfq_number": "RFQ-123",
        "rfq_number": "RFQ-123",
        "reference_number": "RFQ-123",
    }

    result = tender_harvester._lmcp_apply_v50_7_etenders_navigation_gate(item, resolver_overrides={})

    assert result["quote_ready"] is True
    assert result["requires_detail_navigation"] is True
    assert result["pipeline_status"] == "quantity_verification_required"


def test_live_store_preserves_manual_quote_ready_visibility() -> None:
    saved = promote_live_rfqs([
        {
            "title": "Manual quantity verification RFQ",
            "buyer_rfq_number": "RFQ-XYZ",
            "eligible": True,
            "quote_ready": False,
            "pipeline_status": "quantity_verification_required",
            "quantity_safety_status": "quantity_verification_required",
        }
    ])

    item = saved["items"][0]
    assert item["quote_ready"] is True
    assert item["pipeline_status"] in {"quantity_verification_required", "quote_ready_validated"}


def test_live_store_overwrites_generic_urls_for_verified_etenders_documents(tmp_path: Path, monkeypatch) -> None:
    live_store_path = tmp_path / "live_rfqs.json"
    monkeypatch.setattr("app.services.live_rfq_store.LIVE_RFQ_STORE_PATH", live_store_path)

    save_live_rfqs([
        {
            "title": "SUPPLY AND DELIVERY OF JOINTS ON AN AS AND WHEN REQUIRED BASIS FOR A PERIOD OF 5 YEARS AT LETHABO POWER STATION",
            "buyer_rfq_number": "LETHABO-001",
            "detail_url": "https://www.etenders.gov.za/Home/opportunities",
            "document_url": "https://www.etenders.gov.za/Home/opportunities",
            "pipeline_status": "quantity_verification_required",
            "eligible": True,
            "quote_ready": False,
        }
    ])

    saved = promote_live_rfqs([
        {
            "title": "SUPPLY AND DELIVERY OF JOINTS ON AN AS AND WHEN REQUIRED BASIS FOR A PERIOD OF 5 YEARS AT LETHABO POWER STATION",
            "buyer_rfq_number": "LETHABO-001",
            "detail_url": "https://www.etenders.gov.za/Home/DownloadSpec?documentId=155559&source=sharepoint",
            "document_url": "https://www.etenders.gov.za/Home/DownloadSpec?documentId=155559&source=sharepoint",
            "v50_8_discovered_tender_id": "155559",
            "v50_8_extended_resolution_status": "verified_document",
            "downloaded_document_paths": ["/tmp/lethabo.zip"],
            "pipeline_status": "quantity_verification_required",
            "eligible": True,
            "quote_ready": False,
        }
    ])

    item = saved["items"][0]
    assert item["detail_url"].endswith("documentId=155559&source=sharepoint")
    assert item["document_url"].endswith("documentId=155559&source=sharepoint")
    assert item["v50_8_discovered_tender_id"] == "155559"
    assert item["v50_8_extended_resolution_status"] == "verified_document"
    assert item["downloaded_document_paths"] == ["/tmp/lethabo.zip"]


def test_live_store_overwrites_generic_urls_for_verified_tenderdetails_documents(tmp_path: Path, monkeypatch) -> None:
    live_store_path = tmp_path / "live_rfqs.json"
    monkeypatch.setattr("app.services.live_rfq_store.LIVE_RFQ_STORE_PATH", live_store_path)

    save_live_rfqs([
        {
            "title": "SUPPLY AND DELIVERY OF JOINTS ON AN AS AND WHEN REQUIRED BASIS FOR A PERIOD OF 5 YEARS AT LETHABO POWER STATION",
            "buyer_rfq_number": "LETHABO-001",
            "detail_url": "https://www.etenders.gov.za/Home/opportunities",
            "document_url": "https://www.etenders.gov.za/Home/opportunities",
            "pipeline_status": "quantity_verification_required",
            "eligible": True,
            "quote_ready": False,
        }
    ])

    saved = promote_live_rfqs([
        {
            "title": "SUPPLY AND DELIVERY OF JOINTS ON AN AS AND WHEN REQUIRED BASIS FOR A PERIOD OF 5 YEARS AT LETHABO POWER STATION",
            "buyer_rfq_number": "LETHABO-001",
            "detail_url": "https://www.etenders.gov.za/Home/DownloadSpec?documentId=155559&source=sharepoint",
            "document_url": "https://www.etenders.gov.za/Home/DownloadSpec?documentId=155559&source=sharepoint",
            "v50_8_discovered_tender_id": "155559",
            "v50_8_extended_resolution_status": "verified_tenderdetails_document",
            "downloaded_document_paths": ["/tmp/lethabo.zip"],
            "pipeline_status": "quantity_verification_required",
            "eligible": True,
            "quote_ready": False,
        }
    ])

    item = saved["items"][0]
    assert item["detail_url"].endswith("documentId=155559&source=sharepoint")
    assert item["document_url"].endswith("documentId=155559&source=sharepoint")
    assert item["v50_8_discovered_tender_id"] == "155559"
    assert item["v50_8_extended_resolution_status"] == "verified_tenderdetails_document"
    assert item["downloaded_document_paths"] == ["/tmp/lethabo.zip"]
