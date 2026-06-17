from __future__ import annotations

import json
from pathlib import Path

from scripts.repair_refresh_bundle_source_artifacts import repair_refresh_bundle_source_artifacts


def test_repair_refresh_bundle_source_artifacts_adds_root_source_files(tmp_path: Path) -> None:
    root = tmp_path / "runtime" / "manual_production" / "submission_packages" / "FRESH_REFRESH_001"
    nested = root / "source_quotes"
    nested.mkdir(parents=True, exist_ok=True)
    (nested / "FRESH_REFRESH_001__source_rfq.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
    (nested / "FRESH_REFRESH_001__source_rfq_boq.txt").write_text(
        "Pricing Schedule\n\nItem 1: Example\nQuantity: 1\nUnit: Each\nUnit Price: 10.00\nLine Total: 10.00\n",
        encoding="utf-8",
    )
    (root / "FRESH_REFRESH_001__quote_pack.json").write_text(
        json.dumps({"title": "Example RFQ", "buyer_name": "Buyer"}),
        encoding="utf-8",
    )
    (root / "FRESH_REFRESH_001__buyer_pricing_schedule.csv").write_text(
        "line_no,description,quantity,unit_price,line_total\n1,Example,1,10,10\n",
        encoding="utf-8",
    )
    (root / "FRESH_REFRESH_001__submission_package_manifest.json").write_text(
        json.dumps({"source_quote_entries": [str(nested / "FRESH_REFRESH_001__source_rfq.pdf")]}),
        encoding="utf-8",
    )

    report = repair_refresh_bundle_source_artifacts(tmp_path / "runtime" / "manual_production" / "submission_packages")

    assert report["repaired_count"] == 1
    assert (root / "FRESH_REFRESH_001__source_rfq.pdf").exists()
    assert (root / "FRESH_REFRESH_001__source_rfq_boq.txt").exists()
    manifest = json.loads((root / "FRESH_REFRESH_001__submission_package_manifest.json").read_text(encoding="utf-8"))
    assert str(root / "FRESH_REFRESH_001__source_rfq.pdf") in manifest["source_quote_entries"]
    assert str(root / "FRESH_REFRESH_001__source_rfq_boq.txt") in manifest["source_quote_entries"]

