import json
import subprocess
import sys
from pathlib import Path

from scripts.migrate_historical_rfqs import classify_records


def test_migration_union_and_intersections_are_valid():
    report = classify_records(
        [
            {"rfq_number": "A", "title": "Supply and delivery RFQ", "closing_date": "2026-08-01", "status": "Published"},
            {"rfq_number": "B", "title": "Supply and delivery RFQ", "closing_date": "2026-01-01", "status": "Published"},
            {"rfq_number": "C", "title": "Supply and delivery RFQ", "closing_date": "", "status": "Published"},
        ]
    )
    assert report["counts"]["total"] == 3
    assert report["counts"]["active"] == 1
    assert report["counts"]["historical"] == 1
    assert report["counts"]["review_required"] == 1
    assert report["union_verified"] is True
    assert report["intersections_empty"] is True


def test_migration_import_has_no_runtime_side_effects():
    assert Path("runtime/live_rfqs.json").exists()


def test_migration_cli_dry_run_uses_explicit_fixture_paths(tmp_path):
    live_store = tmp_path / "live_rfqs.json"
    lifecycle_store = tmp_path / "rfqs.json"
    historical_store = tmp_path / "historical_rfqs.json"
    review_store = tmp_path / "classification_review_rfqs.json"
    json_report = tmp_path / "preview.json"
    csv_report = tmp_path / "preview.csv"

    live_store.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "rfq_number": "A",
                        "title": "Supply and delivery RFQ",
                        "closing_date": "2026-08-01",
                        "status": "Published",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    lifecycle_store.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "rfq_number": "B",
                        "title": "Supply and delivery RFQ",
                        "closing_date": "2026-01-01",
                        "status": "Published",
                    },
                    {
                        "rfq_number": "C",
                        "title": "Supply and delivery RFQ",
                        "closing_date": "",
                        "status": "Published",
                    },
                    {
                        "rfq_number": "A",
                        "title": "Supply and delivery RFQ duplicate",
                        "closing_date": "2026-08-01",
                        "status": "Published",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    before_live = live_store.read_text(encoding="utf-8")
    before_lifecycle = lifecycle_store.read_text(encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.migrate_historical_rfqs",
            "--dry-run",
            "--live-store",
            str(live_store),
            "--lifecycle-store",
            str(lifecycle_store),
            "--historical-store",
            str(historical_store),
            "--review-store",
            str(review_store),
            "--json-report",
            str(json_report),
            "--csv-report",
            str(csv_report),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["counts"]["active"] == 2
    assert payload["counts"]["historical"] == 1
    assert payload["counts"]["review_required"] == 1
    assert payload["counts"]["duplicate_canonical_ids"] == 1
    assert payload["union_verified"] is True
    assert payload["intersections_empty"] is True
    assert json_report.exists()
    assert csv_report.exists()
    assert not historical_store.exists()
    assert not review_store.exists()
    assert live_store.read_text(encoding="utf-8") == before_live
    assert lifecycle_store.read_text(encoding="utf-8") == before_lifecycle
