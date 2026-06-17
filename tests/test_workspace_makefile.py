from __future__ import annotations

from pathlib import Path


def test_makefile_exposes_pilot_batch_target() -> None:
    makefile = Path("/Users/cash/Documents/Makefile")
    assert makefile.exists()
    content = makefile.read_text(encoding="utf-8")
    assert "pilot-batch:" in content
    assert "scripts/run_workspace_pilot_batch.py" in content
    assert "pilot-batch-one:" in content
    assert "scripts/run_workspace_pilot.py" in content
    assert "pilot-week:" in content
    assert "scripts/run_supervised_pilot_week.py" in content
    assert "pilot-week-dry-run:" in content
    assert "fresh-intake:" in content
    assert "scripts/run_fixture_backed_fresh_intake.py" in content
    assert "queue-refresh:" in content
    assert content.count("queue-refresh:") == 1
    assert "QUEUE_REFRESH_SOURCE_FILE" in content
    assert "bootstrap-live-queue-candidates:" in content
    assert "scripts/bootstrap_remaining_live_queue_candidates.py" in content
    assert "normalize-live-queue-candidates:" in content
    assert "scripts/normalize_live_queue_candidates.py" in content
    assert "prune-completed-live-queue-candidates:" in content
    assert "scripts/prune_completed_live_queue_candidates.py" in content
    assert "repair-refresh-bundle-source-artifacts:" in content
    assert "scripts/repair_refresh_bundle_source_artifacts.py" in content
    assert "live-queue-status:" in content
    assert "scripts/live_queue_status.py" in content
    assert "HARVEST_SOURCE_FILE" in content
    assert "HARVEST_FALLBACK_FIXTURE" in content
    assert "--harvest-source-file" in content
    assert "--fallback-fixture" in content
    assert "daily-pilot-loop:" in content
    assert "scripts/run_daily_pilot_loop.py" in content
    assert "morning-ritual:" in content
    assert "scripts/check_controlled_operation_readiness.py && \\" in content
    assert "scripts/live_queue_status.py \\" in content
    assert "--fail-if-empty" in content
    assert "app/data/queue_refresh_sources.json" in content
    assert "scripts/run_fixture_backed_fresh_intake.py \\" in content
    assert "--require-live-harvest" in content
    assert "--fresh-only" in content
    assert "controlled-operation-check:" in content
    assert "scripts/check_controlled_operation_readiness.py" in content
