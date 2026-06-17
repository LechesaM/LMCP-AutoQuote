from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.repair_zero_pricing_bundles import repair_bundles


def test_repair_bundles_updates_zero_pricing_files(tmp_path: Path) -> None:
    tender_dir = tmp_path / "TENDER-001"
    tender_dir.mkdir(parents=True)

    pricing_json = tender_dir / "TENDER-001__manual_pricing.json"
    pricing_json.write_text(
        json.dumps(
            {
                "tender_id": "TENDER-001",
                "items": [
                    {"item_number": 1, "description": "A4 copy paper", "quantity": 120, "unit_price": 0, "line_total": 0},
                    {"item_number": 2, "description": "Ballpoint pens", "quantity": 60, "unit_price": 0, "line_total": 0},
                ],
            }
        ),
        encoding="utf-8",
    )

    csv_path = tender_dir / "TENDER-001__buyer_pricing_schedule.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["line_no", "description", "quantity", "unit_price", "line_total"])
        writer.writeheader()
        writer.writerows(
            [
                {"line_no": 1, "description": "A4 copy paper", "quantity": 120, "unit_price": 0, "line_total": 0},
                {"line_no": 2, "description": "Ballpoint pens", "quantity": 60, "unit_price": 0, "line_total": 0},
            ]
        )

    repaired = repair_bundles(tmp_path)

    assert repaired == [tender_dir]

    payload = json.loads(pricing_json.read_text(encoding="utf-8"))
    assert payload["items"][0]["unit_price"] == 100.0
    assert payload["items"][0]["line_total"] == 12000.0
    assert payload["items"][1]["unit_price"] == 50.0
    assert payload["items"][1]["line_total"] == 3000.0

    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["unit_price"] == "100.0"
    assert rows[0]["line_total"] == "12000.0"
    assert rows[1]["unit_price"] == "50.0"
    assert rows[1]["line_total"] == "3000.0"
