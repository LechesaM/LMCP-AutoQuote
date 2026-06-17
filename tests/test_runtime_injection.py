from __future__ import annotations

from pathlib import Path

from app.services import tender_harvester


SMOKE_SOURCE_FILE = Path(__file__).resolve().parents[1] / "app" / "data" / "smoke_harvest_sources.json"


def test_live_harvest_writes_source_health_into_injected_runtime_dir(tmp_path: Path) -> None:
    result = tender_harvester.run_national_tender_radar(
        max_total=2,
        max_per_source=1,
        max_sources_per_cycle=1,
        source_file=str(SMOKE_SOURCE_FILE),
        controlled_mode=False,
        persist_to_live_store=False,
        browser_available=False,
        source_timeout_seconds=3,
        playwright_timeout_ms=5000,
        runtime_dir=str(tmp_path),
        resolver_overrides={
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
        },
    )

    assert result["status"] == "ok"
    assert result["source_health_snapshot_injected"] is False
    assert result["source_timeout_seconds"] == 3
    assert result["playwright_timeout_ms"] == 5000
    assert (tmp_path / "source_health.json").exists()


def test_source_selection_reads_injected_runtime_source_health(tmp_path: Path) -> None:
    source_health_file = tmp_path / "source_health.json"
    source_health_file.write_text(
        """
        {
          "Injected Source": {
            "failure_count": 0,
            "candidate_total": 10,
            "qualified_candidate_total": 4,
            "document_candidate_total": 2,
            "consecutive_empty_runs": 0,
            "last_success_at": "2026-06-02T20:00:00+00:00",
            "last_empty_at": "2026-06-01T20:00:00+00:00"
          }
        }
        """.strip(),
        encoding="utf-8",
    )

    sources = [
        {"name": "Injected Source", "priority": 1, "enabled": True},
        {"name": "Fallback Source", "priority": 2, "enabled": True},
    ]

    selected = tender_harvester.select_sources_for_cycle(
        sources,
        max_sources_per_cycle=1,
        include_bad_sources=False,
        controlled_mode=False,
        source_health_file=source_health_file,
    )

    assert selected[0]["name"] == "Injected Source"


def test_reporting_helpers_use_injected_runtime_source_health(tmp_path: Path) -> None:
    source_health_file = tmp_path / "source_health.json"
    source_health_file.write_text("{}", encoding="utf-8")
    pause_file = tmp_path / "harvester.paused"
    pause_file.write_text("paused", encoding="utf-8")

    harvester_health = tender_harvester.get_harvester_health(runtime_dir=str(tmp_path), source_health_file=source_health_file)
    overview = tender_harvester.get_source_health_overview(
        source_file=str(SMOKE_SOURCE_FILE),
        source_health_file=source_health_file,
    )

    assert harvester_health["status"] == "paused"
    assert harvester_health["pause_file"] == str(pause_file)
    assert harvester_health["source_health_file"] == str(source_health_file)
    assert overview["source_health_file"] == str(source_health_file)
