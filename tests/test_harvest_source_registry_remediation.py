from __future__ import annotations

import json
from pathlib import Path

from app.services import harvest_source_registry_service, tender_harvester


def test_load_harvest_sources_filters_google_search_seed_sources(tmp_path: Path) -> None:
    source_file = tmp_path / "sources.json"
    source_file.write_text(
        json.dumps(
            [
                {"name": "Direct Portal", "url": "https://buyer.example.com/tenders", "enabled": True},
                {"name": "Google Seed", "url": "https://www.google.com/search?q=buyer+tenders+site%3Aza", "enabled": True},
            ]
        ),
        encoding="utf-8",
    )

    loaded = tender_harvester.load_harvest_sources(str(source_file))
    registry_loaded = harvest_source_registry_service.load_harvest_sources(source_file)

    assert [row["name"] for row in loaded] == ["Direct Portal"]
    assert [row["name"] for row in registry_loaded] == ["Direct Portal"]


def test_zero_yield_sources_are_quarantined_after_exploratory_budget_exhausted(tmp_path: Path) -> None:
    source_health_file = tmp_path / "source_health.json"
    source_health_file.write_text(
        json.dumps(
                {
                    "Dead Source": {
                        "scan_total": 30,
                        "scan_count": 30,
                        "candidate_total": 0,
                        "qualified_candidate_total": 0,
                        "document_candidate_total": 0,
                        "consecutive_empty_runs": 30,
                        "last_status": "ok_empty",
                        "last_checked_at": "2026-06-11T00:00:00+00:00",
                        "last_empty_at": "2026-06-11T00:00:00+00:00",
                    }
                }
            ),
        encoding="utf-8",
    )

    row = tender_harvester._v53_source_health_row(  # noqa: SLF001
        {"name": "Dead Source", "url": "https://dead.example.com/tenders", "enabled": True},
        source_health_file=source_health_file,
    )

    assert row["source_quarantine_status"] == "quarantined"
    assert row["source_selection_score"] == 0.0
    assert row["source_operator_action"] == "quarantine"


def test_google_search_source_is_not_selected_for_cycle(tmp_path: Path) -> None:
    source_file = tmp_path / "sources.json"
    source_file.write_text(
        json.dumps(
            [
                {"name": "Direct Portal", "url": "https://buyer.example.com/tenders", "enabled": True, "priority": 5},
                {"name": "Google Seed", "url": "https://www.google.com/search?q=buyer+tenders+site%3Aza", "enabled": True, "priority": 1},
            ]
        ),
        encoding="utf-8",
    )

    sources = tender_harvester.load_harvest_sources(str(source_file))
    selected = tender_harvester.select_sources_for_cycle(sources, max_sources_per_cycle=5)

    assert [row["name"] for row in selected] == ["Direct Portal"]


def test_curated_live_source_marker_resolves_to_1040_sources() -> None:
    curated_marker = harvest_source_registry_service.get_curated_live_source_file()

    registry_loaded = harvest_source_registry_service.load_harvest_sources(curated_marker)
    tender_loaded = tender_harvester.load_harvest_sources(curated_marker)

    assert curated_marker == "curated/live/default"
    assert len(registry_loaded) == 1040
    assert len(tender_loaded) == 1040


def test_sync_default_registry_file_writes_curated_source_payload(tmp_path: Path) -> None:
    registry_path = tmp_path / "harvest_sources.json"

    payload = harvest_source_registry_service.sync_default_registry_file(registry_path)
    written = json.loads(registry_path.read_text(encoding="utf-8"))

    assert payload["source_count"] == 1040
    assert written["source_count"] == 1040
    assert len(written["sources"]) == 1040
    assert all("google.com/search" not in row["url"] for row in written["sources"])
