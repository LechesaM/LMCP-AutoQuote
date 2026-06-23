from __future__ import annotations

import json
from pathlib import Path

from app.services import operational_rehearsal_service as rehearsal_mod


def _write_run(root: Path, run_id: str, *, status: str = "PASS", warn: int = 0, fail: int = 0) -> Path:
    run_dir = root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "generated_at": "2026-06-23T09:30:20+00:00",
        "scenario_count": 2,
        "scenario_statuses": {
            "normal_rfq": "PASS",
            "retry_rehearsal": status,
            "queue_congestion_rehearsal": "PASS",
            "worker_recovery_rehearsal": "PASS",
            "dead_letter_rehearsal": "PASS",
            "rollback_rehearsal": "PASS",
            "telemetry_validation_rehearsal": "PASS",
        },
        "scenario_summaries": [
            {"index": 1, "name": "normal_rfq", "status": "PASS", "warnings": 0, "failures": 0, "checks": 4, "evidence_dir": str(run_dir / "normal_rfq")},
            {"index": 2, "name": "retry_rehearsal", "status": status, "warnings": warn, "failures": fail, "checks": 3, "evidence_dir": str(run_dir / "retry_rehearsal")},
        ],
        "overall_counts": {"PASS": 10, "WARN": warn, "FAIL": fail},
        "dry_run_guarantees": {
            "live_submissions": False,
            "production_queues": False,
            "production_databases": False,
            "irreversible_operations": False,
        },
        "environment_contract": {"path": "/tmp/staging.env"},
    }
    (run_dir / "operational_rehearsal_summary.json").write_text(json.dumps(payload), encoding="utf-8")
    (run_dir / "environment_contract.json").write_text(json.dumps({"path": "/tmp/staging.env"}), encoding="utf-8")
    (run_dir / "artifact-a.json").write_text("{}", encoding="utf-8")
    return run_dir


def test_operational_rehearsal_service_reads_latest_and_history(tmp_path, monkeypatch) -> None:
    root = tmp_path / "runtime" / "staging" / "rehearsals"
    _write_run(root, "20260623T090000Z-operational-aaaa1111")
    latest_dir = _write_run(root, "20260623T093020Z-operational-bbbb2222", status="WARN", warn=1, fail=0)
    monkeypatch.setattr(rehearsal_mod, "REHEARSAL_RUNTIME_DIR", root)

    service = rehearsal_mod.OperationalRehearsalService()
    latest = service.latest_rehearsal()
    history = service.list_rehearsals(limit=2)
    run = service.get_rehearsal(latest_dir.name)

    assert latest["status"] == "ok"
    assert latest["run_id"] == latest_dir.name
    assert latest["operational_health"]["status"] == "degraded"
    assert latest["drill_outcomes"]["retry_drill"]["status"] == "WARN"
    assert latest["timeline"][0]["scenario"] == "normal_rfq"
    assert latest["artifact_summary"]["artifact_count"] >= 2

    assert history["status"] == "ok"
    assert history["count"] == 2
    assert history["runs"][0]["run_id"] == latest_dir.name

    assert run["status"] == "ok"
    assert run["run"]["run_id"] == latest_dir.name
    assert run["run"]["warning_banners"]


def test_operational_rehearsal_service_handles_missing_runs(tmp_path, monkeypatch) -> None:
    root = tmp_path / "runtime" / "staging" / "rehearsals"
    monkeypatch.setattr(rehearsal_mod, "REHEARSAL_RUNTIME_DIR", root)

    service = rehearsal_mod.OperationalRehearsalService()
    latest = service.latest_rehearsal()
    history = service.list_rehearsals()
    run = service.get_rehearsal("missing")

    assert latest["status"] == "not_found"
    assert history["count"] == 0
    assert run["status"] == "not_found"
