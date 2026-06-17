from __future__ import annotations

import json
from pathlib import Path

from app.services import tender_harvester


def test_controlled_source_selection_ignores_runtime_health(tmp_path: Path, monkeypatch) -> None:
    source_health_file = tmp_path / "source_health.json"
    source_health_file.write_text(
        json.dumps(
            {
                "Alpha": {"failure_count": 99, "candidate_total": 0},
                "Beta": {"failure_count": 1, "candidate_total": 999},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(tender_harvester, "SOURCE_HEALTH_FILE", source_health_file)

    sources = [
        {"name": "Zulu", "source_name": "Zulu", "priority": 2, "intelligence_score": 50, "enabled": True, "url": "file:///tmp/zulu.html"},
        {"name": "Alpha", "source_name": "Alpha", "priority": 1, "intelligence_score": 40, "enabled": True, "url": "file:///tmp/alpha.html"},
        {"name": "Beta", "source_name": "Beta", "priority": 1, "intelligence_score": 90, "enabled": True, "url": "file:///tmp/beta.html"},
    ]

    first = tender_harvester.select_sources_for_cycle(sources, max_sources_per_cycle=3, controlled_mode=True)

    source_health_file.write_text(
        json.dumps(
            {
                "Alpha": {"failure_count": 0, "candidate_total": 5},
                "Beta": {"failure_count": 0, "candidate_total": 0},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    second = tender_harvester.select_sources_for_cycle(sources, max_sources_per_cycle=3, controlled_mode=True)

    assert [source["name"] for source in first] == ["Beta", "Alpha", "Zulu"]
    assert [source["name"] for source in second] == ["Beta", "Alpha", "Zulu"]


def test_dashboard_resolver_status_reports_current_resolver_bundle() -> None:
    import os

    os.environ.setdefault("LMCP_PROJECT_ROOT", "/Users/cash/Documents")
    os.environ.setdefault("LMCP_RUNTIME_DIR", "/Users/cash/Documents/runtime")
    from app import dashboard_api

    payload = dashboard_api.dashboard_resolver_status()

    assert payload["status"] == "ok"
    assert payload["resolvers"]["v50_8_true_detail"]["status"] == "ok"
    assert payload["resolvers"]["v50_8_1_ajax"]["status"] == "ok"
    assert payload["resolvers"]["v50_8_2_reconstruction"]["status"] == "ok"
    assert payload["resolvers"]["v50_9_1_tenderdetails"]["status"] == "ok"
    assert payload["resolvers"]["v50_9_6_hidden_api"]["status"] == "ok"
