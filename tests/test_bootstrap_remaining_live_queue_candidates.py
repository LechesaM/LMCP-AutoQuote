from __future__ import annotations

import json
from pathlib import Path

from scripts.bootstrap_remaining_live_queue_candidates import bootstrap_remaining_live_queue_candidates


def test_bootstrap_remaining_live_queue_candidates_creates_bundle_and_pricing(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    manual_root = runtime_root / "manual_production"
    manual_root.mkdir(parents=True, exist_ok=True)
    queue_file = runtime_root / "live_rfqs.json"
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text(
        json.dumps(
            {
                "status": "ok",
                "count": 1,
                "items": [
                    {
                        "rfq_id": "LIVE-001",
                        "title": "Live Import RFQ",
                        "source_name": "Imported Portal",
                        "status": "live",
                        "eligible": True,
                        "quote_ready": False,
                        "estimated_contract_value": 12345,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    from scripts import bootstrap_remaining_live_queue_candidates as module

    module.MANUAL_PRODUCTION_ROOT = manual_root
    module.SOURCE_BUNDLE_ROOT = manual_root / "source_bundle_repairs"
    module.SUBMISSION_PACKAGE_ROOT = manual_root / "submission_packages"

    bootstrapped = bootstrap_remaining_live_queue_candidates(queue_file)

    assert bootstrapped == ["LIVE-001"]
    assert (module.SOURCE_BUNDLE_ROOT / "LIVE-001" / "LIVE-001_overview.txt").exists()
    pdf_bytes = (module.SOURCE_BUNDLE_ROOT / "LIVE-001" / "LIVE-001_source_rfq.pdf").read_bytes()
    assert pdf_bytes.startswith(b"%PDF")
    assert b"Item 1: Supply and Delivery of Office Consumables" in pdf_bytes
    assert b"Quantity: 1" in pdf_bytes
    assert b"Unit Price:" in pdf_bytes
    pricing = json.loads((module.SUBMISSION_PACKAGE_ROOT / "LIVE-001" / "LIVE-001__manual_pricing.json").read_text(encoding="utf-8"))
    assert pricing["items"][0]["unit_price"] > 0
    assert pricing["items"][0]["line_total"] > 0
