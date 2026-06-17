from __future__ import annotations

import json
import os
from pathlib import Path

from app.services.harvest_scheduler_service import (
    _normalize_manual_quote_ready_projection,
    get_latest_scheduled_harvest_summaries,
)


def test_latest_scheduled_harvest_prefers_newest_artifact_and_cycles_fallback(tmp_path: Path) -> None:
    scheduled_root = tmp_path / "harvest_runs" / "scheduled"
    old_run_dir = scheduled_root / "scheduled_harvest_20260608T050000Z"
    new_run_dir = scheduled_root / "scheduled_harvest_20260611T145703Z"
    old_run_dir.mkdir(parents=True)
    new_run_dir.mkdir(parents=True)

    old_summary = {
        "status": "ok",
        "run_id": "scheduled_harvest_20260608T050000Z",
        "started_at": "2026-06-08T05:00:00.062744+00:00",
        "completed_at": "2026-06-08T05:15:13.593713+00:00",
        "source_count": 1325,
        "controlled_mode": False,
        "persist_to_live_store": True,
    }
    (old_run_dir / "summary.json").write_text(json.dumps(old_summary), encoding="utf-8")

    new_cycle = {
        "cycle": 1,
        "cycle_started_at": "2026-06-11T14:57:03.746869+00:00",
        "completed_at": "2026-06-11T14:58:08.012444+00:00",
        "summary": {
            "status": "ok",
            "run_started_at": "2026-06-11T14:57:03.746884+00:00",
            "run_id": "scheduled_harvest_20260611T145703Z",
            "source_count": 66,
            "selected_source_count": 10,
            "harvested_total": 5,
            "screened_out_total": 5,
            "eligible_total": 0,
            "controlled_mode": False,
            "persist_to_live_store": True,
        },
    }
    (new_run_dir / "cycles.jsonl").write_text(json.dumps(new_cycle) + "\n", encoding="utf-8")

    summary_path = old_run_dir / "summary.json"
    cycles_path = new_run_dir / "cycles.jsonl"
    os.utime(summary_path, (1_000_000_000, 1_000_000_000))
    os.utime(cycles_path, (1_000_100_000, 1_000_100_000))

    result = get_latest_scheduled_harvest_summaries(runtime_dir=str(tmp_path))

    assert result["latest_any"]["run_id"] == "scheduled_harvest_20260611T145703Z"
    assert result["latest_any"]["source_count"] == 66
    assert result["latest_regular"]["run_id"] == "scheduled_harvest_20260611T145703Z"
    assert result["run_count"] == 2


def test_quote_ready_total_projects_from_live_store_items_when_summary_items_absent() -> None:
    projected = _normalize_manual_quote_ready_projection(
        {
            "eligible_total": 1,
            "quote_ready_total": 0,
            "live_store_result": {
                "status": "ok",
                "items": [
                    {
                        "eligible": True,
                        "quote_ready": True,
                        "pipeline_status": "quote_ready_validated",
                    }
                ],
            },
        }
    )

    assert projected["quote_ready_total"] == 1
