from __future__ import annotations

import csv
from pathlib import Path

from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.services import supplier_quote_auto_ingestion_service as auto_ingestion


def _prepare_runtime(monkeypatch, tmp_path: Path) -> Path:
    runtime_dir = tmp_path / "runtime"
    monthly_quotes_dir = tmp_path / "monthly_quotes"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    monthly_quotes_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("LMCP_MONTHLY_QUOTES_DIR", str(monthly_quotes_dir))
    get_runtime_paths.cache_clear()
    get_runtime_config.cache_clear()
    return monthly_quotes_dir


def _write_csv_quote(path: Path, supplier_name: str, quote_reference: str, rows: list[tuple[str, float, str, float]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["supplier_name", "quote_reference", "description", "quantity", "unit", "unit_price", "line_total"],
        )
        writer.writeheader()
        for description, quantity, unit, unit_price in rows:
            writer.writerow(
                {
                    "supplier_name": supplier_name,
                    "quote_reference": quote_reference,
                    "description": description,
                    "quantity": quantity,
                    "unit": unit,
                    "unit_price": unit_price,
                    "line_total": round(quantity * unit_price, 2),
                }
            )


def test_supplier_quote_auto_ingestion_scans_nested_workspaces(monkeypatch, tmp_path: Path) -> None:
    monthly_quotes_dir = _prepare_runtime(monkeypatch, tmp_path)
    folder = monthly_quotes_dir / "2026-05" / "RFQ-222__LMCP-222"
    folder.mkdir(parents=True, exist_ok=True)

    _write_csv_quote(
        folder / "alpha_quote.csv",
        "Alpha Supplies",
        "ALPHA-222",
        [("Paper reams", 10, "Ream", 85.0), ("Ink cartridges", 4, "Each", 180.0)],
    )
    _write_csv_quote(
        folder / "bravo_quote.csv",
        "Bravo Office",
        "BRAVO-222",
        [("Paper reams", 10, "Ream", 94.0), ("Ink cartridges", 4, "Each", 210.0)],
    )

    detail_calls = []
    bundle_calls = []
    package_calls = []
    audit_calls = []

    def fake_detail(tender_id: str):
        detail_calls.append(tender_id)
        return {
            "tender_id": tender_id,
            "harvest_enrichment": {
                "live_rfq": {
                    "items": [
                        {"description": "Paper reams", "quantity": 10, "unit": "Ream"},
                        {"description": "Ink cartridges", "quantity": 4, "unit": "Each"},
                    ]
                }
            },
        }

    def fake_bundle(detail):
        bundle_calls.append(detail)
        return {"review_ready": True, "submission_ready": False, "bundle_dir": str(tmp_path / "review_bundle")}

    def fake_package(detail):
        package_calls.append(detail)
        return {"submission_ready": True, "package_dir": str(tmp_path / "submission_package")}

    def fake_audit_event(**kwargs):
        payload = {"id": f"audit-{len(audit_calls) + 1}", **kwargs}
        audit_calls.append(payload)
        return payload

    monkeypatch.setattr(auto_ingestion, "get_operator_workflow_detail", fake_detail)
    monkeypatch.setattr(auto_ingestion, "build_review_ready_bundle", fake_bundle)
    monkeypatch.setattr(auto_ingestion, "build_submission_package", fake_package)
    monkeypatch.setattr(auto_ingestion, "append_audit_event", fake_audit_event)

    result = auto_ingestion.scan_quote_folders(root_path=monthly_quotes_dir)

    assert result["status"] == "ok"
    assert result["processed_count"] == 1
    assert result["errors"] == []
    assert detail_calls == ["RFQ-222", "RFQ-222"]
    assert bundle_calls and package_calls
    assert audit_calls and audit_calls[0]["event_type"] == "supplier_quote_auto_ingestion"
    assert result["processed"][0]["review_ready"] is True
    assert result["processed"][0]["submission_ready"] is True
    assert (folder / "quote_comparison.json").exists()
    assert Path(auto_ingestion._runtime_state_file()).exists()
    assert result["watch_status"]["last_scan_at"]
    assert result["watch_status"]["files_scanned"] == 2
    assert result["watch_status"]["new_files_detected"] == 2
    assert result["watch_status"]["unchanged_files_skipped"] == 0
    assert result["watch_status"]["skipped_files"] == 0
    assert result["watch_status"]["failed_files"] == 0
    assert result["watch_status"]["last_generated_comparison_path"].endswith("quote_comparison.json")
    assert result["watch_status"]["comparison_path"].endswith("quote_comparison.json")
    assert result["watch_status"]["last_regenerated_package_path"]
    assert result["watch_status"]["package_path"]
    assert result["watch_status"]["last_audit_event_id"]
    assert result["watch_status"]["audit_event_id"]
    assert result["watch_status"]["folders"]
    assert result["watch_status"]["folders"][0]["folder"] == str(folder)
    assert result["watch_status"]["folders"][0]["comparison_path"].endswith("quote_comparison.json")
    assert result["watch_status"]["folders"][0]["package_path"]
