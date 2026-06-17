from __future__ import annotations

import csv
from pathlib import Path

from app.core.runtime_config import get_runtime_config
from app.core.runtime_paths import get_runtime_paths
from app.services import supplier_quote_intelligence_service as intelligence


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


def _write_csv_quote(path: Path, supplier_name: str, quote_reference: str, totals: list[tuple[str, float, str, float]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["supplier_name", "quote_reference", "description", "quantity", "unit", "unit_price", "line_total"],
        )
        writer.writeheader()
        for description, quantity, unit, unit_price in totals:
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


def _write_html_mislabeled_pdf(path: Path) -> None:
    path.write_bytes(b"<!doctype html><html><body><h1>Not a PDF</h1></body></html>")


def test_supplier_quote_intelligence_runs_end_to_end(monkeypatch, tmp_path: Path) -> None:
    monthly_quotes_dir = _prepare_runtime(monkeypatch, tmp_path)
    folder = monthly_quotes_dir / "2026-05" / "RFQ-100__LMCP-100"
    folder.mkdir(parents=True, exist_ok=True)

    _write_csv_quote(
        folder / "alpha_quote.csv",
        "Alpha Supplies",
        "ALPHA-100",
        [("Paper reams", 10, "Ream", 85.0), ("Ink cartridges", 4, "Each", 180.0)],
    )
    _write_csv_quote(
        folder / "bravo_quote.csv",
        "Bravo Office",
        "BRAVO-100",
        [("Paper reams", 10, "Ream", 94.0), ("Ink cartridges", 4, "Each", 210.0)],
    )

    result = intelligence.analyze_supplier_quote_folder(
        folder,
        payload={
            "items": [
                {"description": "Paper reams", "quantity": 10, "unit": "Ream"},
                {"description": "Ink cartridges", "quantity": 4, "unit": "Each"},
            ]
        },
        margin_percent=25.0,
        minimum_profit=30000.0,
    )

    assert result["status"] == "ok"
    assert result["processed_file_count"] == 2
    assert result["supplier_quotes"]
    assert result["supplier_quote_comparison"]["comparison_rows"]
    assert result["pricing_schedule"]["items"]
    assert result["line_item_comparison"]
    assert result["artifacts"]["summary_path"]
    assert Path(result["artifacts"]["summary_path"]).exists()
    assert Path(result["artifacts"]["comparison_path"]).exists()
    assert Path(result["artifacts"]["pricing_schedule_path"]).exists()
    assert Path(result["artifacts"]["workspace_comparison_path"]).exists()
    assert result["supplier_quote_comparison"]["recommended_supplier"]["supplier_name"] == "Alpha Supplies"

    status = intelligence.SupplierQuoteIntelligenceService.get_status()
    assert status["status"] == "ok"
    assert status["last_run_at"]
    assert status["last_workspace"] == str(folder)
    assert status["last_tender_id"] == "RFQ-100"
    assert status["last_status"] == "ok"
    assert status["last_error"] == ""
    assert status["files_processed"] == 2
    assert status["comparison_path"].endswith("comparison.json")
    assert status["schedule_path"].endswith("pricing_schedule.json")
    assert status["artifact_count"] >= 1


def test_supplier_quote_intelligence_skips_mislabeled_pdf_html_with_warning(monkeypatch, tmp_path: Path) -> None:
    monthly_quotes_dir = _prepare_runtime(monkeypatch, tmp_path)
    folder = monthly_quotes_dir / "2026-05" / "RFQ-600__LMCP-600"
    folder.mkdir(parents=True, exist_ok=True)

    _write_csv_quote(
        folder / "alpha_quote.csv",
        "Alpha Supplies",
        "ALPHA-600",
        [("Paper reams", 10, "Ream", 85.0)],
    )
    _write_html_mislabeled_pdf(folder / "broken_quote.pdf")

    result = intelligence.analyze_supplier_quote_folder(
        folder,
        payload={
            "items": [
                {"description": "Paper reams", "quantity": 10, "unit": "Ream"},
            ],
            "attachment_warnings": ["Attachment broken_quote.pdf is mislabeled as PDF but contains HTML content; skipped from parsing."],
        },
        margin_percent=25.0,
        minimum_profit=30000.0,
    )

    assert result["status"] == "ok"
    assert result["discovered_file_count"] == 2
    assert result["processed_file_count"] == 1
    assert result["failed_file_count"] == 0
    assert result["warnings"]
    assert any("mislabeled as PDF" in warning for warning in result["warnings"])
    assert result["invalid_attachments"]
    assert result["invalid_attachments"][0]["attachment_status"] == "invalid_attachment_type"
    assert Path(result["artifacts"]["summary_path"]).exists()
    assert Path(result["artifacts"]["workspace_comparison_path"]).exists()
    assert result["supplier_quotes"]
