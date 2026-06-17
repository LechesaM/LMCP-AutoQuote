from __future__ import annotations

import json
from pathlib import Path

from app.services.acquisition_backed_validation_service import build_acquisition_backed_validation_report


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_live_item(tmp_path: Path, rfq_id: str, *, downloaded: bool, acquirable: bool = False) -> dict:
    pack_root = tmp_path / rfq_id / "quote_pack"
    _write(pack_root / "quote_pack.pdf", "pdf")
    _write(pack_root / "quote_pack.json", "{}")
    _write(pack_root / "buyer_pricing_schedule.csv", "line,item\n1,Widget\n")
    _write(pack_root / "submission_package.zip", "zip")
    _write(pack_root / "submission_package_manifest.json", "{}")
    main_doc = tmp_path / rfq_id / "main.docx"
    _write(main_doc, "docx")

    item = {
        "rfq_id": rfq_id,
        "title": f"{rfq_id} title",
        "buyer_name": "Buyer",
        "buyer_pack_downloaded": downloaded,
        "buyer_pack_verified": downloaded,
        "buyer_pack_source": str(main_doc),
        "document_acquisition_status": "downloaded" if downloaded else ("ready" if acquirable else "not_attempted"),
        "document_acquisition_result": {
            "downloaded_files": [{"path": str(main_doc)}] if downloaded else [],
        },
        "boq_detected": downloaded,
        "pricing_schedule_detected": downloaded,
        "returnables_detected": downloaded,
        "quote_pack_generated": downloaded,
        "quote_pack_path": str(pack_root / "quote_pack.pdf"),
        "quote_pack_artifact_exists": downloaded,
        "quote_pack_artifact_size_bytes": (pack_root / "quote_pack.pdf").stat().st_size,
        "quote_pack_readiness_score": 100 if downloaded else 0,
        "document_inventory_paths_limited": [str(main_doc)],
        "detected_document_types": ["pdf", "docx", "xlsx"] if downloaded else [],
        "updated_at": "2026-06-15T00:00:00Z",
    }
    if downloaded:
        item["buyer_pack_path"] = str(main_doc)
        item["document_acquisition_result"]["main_document_path"] = str(main_doc)
    if acquirable and not downloaded:
        item.update(
            {
                "document_url": "https://example.invalid/doc",
                "detail_url": "https://example.invalid/detail",
                "source_url": "https://example.invalid/source",
            }
        )
    return item


def _build_manual_record(tmp_path: Path, tender_id: str) -> dict:
    root = tmp_path / tender_id
    source_pdf = root / f"{tender_id}__source_rfq.pdf"
    source_boq = root / f"{tender_id}__source_rfq_boq.txt"
    quote_pdf = root / f"{tender_id}__quote_pack.pdf"
    quote_json = root / f"{tender_id}__quote_pack.json"
    pricing_csv = root / f"{tender_id}__buyer_pricing_schedule.csv"
    submission_zip = root / f"{tender_id}__submission_package.zip"
    manifest = root / f"{tender_id}__submission_package_manifest.json"
    _write(source_pdf, "source")
    _write(source_boq, "boq")
    _write(quote_pdf, "quote pdf")
    _write(quote_json, "{}")
    _write(pricing_csv, "line,item\n1,Widget\n")
    _write(submission_zip, "zip")
    _write(manifest, "{}")
    return {
        "kind": "manual",
        "tender_id": tender_id,
        "tender_root": str(root),
        "quote_pack_generated": True,
        "submission_pack_generated": True,
        "quote_pack_quality_status": "approval_ready",
        "approval_blocked": False,
        "quote_pack_quality_reason": "quote pack is priced and has a non-zero total",
        "human_approval_required": True,
        "human_approval_granted": False,
        "final_submission_attempted": False,
        "status": "pending_human_approval",
        "source_evidence": [str(source_pdf), str(source_boq)],
    }


def test_acquisition_backed_validation_selects_evidence_backed_rows_and_excludes_random_live_rows(tmp_path: Path) -> None:
    downloaded = _build_live_item(tmp_path, "LIVE-DOWNLOADED", downloaded=True)
    acquirable = _build_live_item(tmp_path, "LIVE-ACQUIRABLE", downloaded=False, acquirable=True)
    random_live = {
        "rfq_id": "LIVE-RANDOM",
        "title": "Random live RFQ",
        "buyer_name": "Buyer",
        "buyer_pack_downloaded": False,
        "document_acquisition_status": "not_attempted",
        "updated_at": "2026-06-15T00:00:00Z",
    }
    manual = _build_manual_record(tmp_path, "FRESH_INTAKE_20260608T215127Z_661")

    output = tmp_path / "report.json"
    report = build_acquisition_backed_validation_report(
        limit=2,
        live_items=[downloaded, acquirable, random_live],
        pilot_records=[manual],
        output_path=str(output),
    )

    assert report["status"] == "ok"
    assert report["selected_count"] == 2
    assert report["selection_summary"]["random_live_count"] == 1
    assert report["selection_confusion_guard"]["random_live_rfqs_excluded"] == 1
    assert any(item["kind"] == "manual" and item["artifact_evidence_ok"] for item in report["items"])
    assert all(item["id"] != "LIVE-RANDOM" for item in report["items"])
    assert all(item["artifact_evidence_ok"] for item in report["items"])
    assert output.exists()


def test_acquisition_backed_validation_persists_artifact_evidence_and_keeps_submission_locked(tmp_path: Path) -> None:
    live = _build_live_item(tmp_path, "FIN-SCM-TEN-0236", downloaded=True)
    manual = _build_manual_record(tmp_path, "FRESH-IMPORT-20260608231426-96881")
    output = tmp_path / "audit" / "acquisition_backed_validation_report_10.json"

    report = build_acquisition_backed_validation_report(
        limit=2,
        live_items=[live],
        pilot_records=[manual],
        output_path=str(output),
    )

    persisted = json.loads(output.read_text(encoding="utf-8"))

    assert report["status"] == "ok"
    assert persisted["status"] == "ok"
    assert report["buyer_pack_downloaded_count"] == 2
    assert report["document_intelligence_pass_count"] == 2
    assert report["quote_pack_generated_count"] == 2
    assert report["human_approval_required_count"] == 2
    assert report["final_submission_attempted_count"] == 0
    assert report["autonomous_submission_count"] == 0
    assert report["artifact_evidence_failures"] == 0
    assert all(item["final_autonomous_submission_locked"] for item in report["items"])
    assert all(item["human_approval_required"] for item in report["items"])
    assert all(item["quote_pack_generated"] for item in report["items"])
    assert all(item["document_intelligence_pass"] for item in report["items"])
    assert report["items"][0]["quote_pack_artifact_exists"] is True


def test_acquisition_backed_validation_skips_partial_live_downloads_when_fully_evidence_backed_items_exist(tmp_path: Path) -> None:
    partial_live = _build_live_item(tmp_path, "LIVE-PARTIAL", downloaded=True)
    partial_live.update(
        {
            "boq_detected": False,
            "pricing_schedule_detected": False,
            "returnables_detected": False,
            "quote_pack_generated": False,
            "quote_pack_artifact_exists": False,
            "quote_pack_readiness_score": 40,
        }
    )
    good_live = _build_live_item(tmp_path, "LIVE-GOOD", downloaded=True)
    manual = _build_manual_record(tmp_path, "FRESH_REFRESH_20260611T101127Z_69711")

    report = build_acquisition_backed_validation_report(
        limit=2,
        live_items=[partial_live, good_live],
        pilot_records=[manual],
    )

    assert report["status"] == "ok"
    assert report["selected_count"] == 2
    assert all(item["artifact_evidence_ok"] for item in report["items"])
    assert all(item["document_intelligence_pass"] for item in report["items"])
    assert report["artifact_evidence_failures"] == 0
