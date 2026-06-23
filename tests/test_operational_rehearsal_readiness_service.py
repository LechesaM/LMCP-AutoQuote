from __future__ import annotations

import json
from pathlib import Path

from app.services import operational_rehearsal_service as rehearsal_mod


def _write_run(root: Path, run_id: str, statuses: dict[str, str], counts: dict[str, int]) -> Path:
    run_dir = root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "generated_at": "2026-06-23T09:30:20+00:00",
        "scenario_count": 7,
        "scenario_statuses": statuses,
        "scenario_summaries": [
            {"index": 1, "name": "normal_rfq", "status": statuses.get("normal_rfq", "PASS"), "warnings": 0, "failures": 0, "checks": 4, "evidence_dir": str(run_dir / "normal_rfq")},
            {"index": 2, "name": "retry_rehearsal", "status": statuses.get("retry_rehearsal", "PASS"), "warnings": 0, "failures": 0, "checks": 3, "evidence_dir": str(run_dir / "retry_rehearsal")},
            {"index": 3, "name": "queue_congestion_rehearsal", "status": statuses.get("queue_congestion_rehearsal", "PASS"), "warnings": 0, "failures": 0, "checks": 3, "evidence_dir": str(run_dir / "queue_congestion_rehearsal")},
            {"index": 4, "name": "worker_recovery_rehearsal", "status": statuses.get("worker_recovery_rehearsal", "PASS"), "warnings": 0, "failures": 0, "checks": 3, "evidence_dir": str(run_dir / "worker_recovery_rehearsal")},
            {"index": 5, "name": "dead_letter_rehearsal", "status": statuses.get("dead_letter_rehearsal", "PASS"), "warnings": 0, "failures": 0, "checks": 3, "evidence_dir": str(run_dir / "dead_letter_rehearsal")},
            {"index": 6, "name": "rollback_rehearsal", "status": statuses.get("rollback_rehearsal", "PASS"), "warnings": 0, "failures": 0, "checks": 3, "evidence_dir": str(run_dir / "rollback_rehearsal")},
            {"index": 7, "name": "telemetry_validation_rehearsal", "status": statuses.get("telemetry_validation_rehearsal", "PASS"), "warnings": 0, "failures": 0, "checks": 3, "evidence_dir": str(run_dir / "telemetry_validation_rehearsal")},
        ],
        "overall_counts": counts,
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


def test_operational_rehearsal_service_produces_readiness_summary(tmp_path, monkeypatch) -> None:
    root = tmp_path / "runtime" / "staging" / "rehearsals"
    _write_run(
        root,
        "20260623T090000Z-operational-aaaa1111",
        {
            "normal_rfq": "PASS",
            "retry_rehearsal": "PASS",
            "queue_congestion_rehearsal": "PASS",
            "worker_recovery_rehearsal": "PASS",
            "dead_letter_rehearsal": "PASS",
            "rollback_rehearsal": "PASS",
            "telemetry_validation_rehearsal": "PASS",
        },
        {"PASS": 54, "WARN": 0, "FAIL": 0},
    )
    latest_dir = _write_run(
        root,
        "20260623T093020Z-operational-bbbb2222",
        {
            "normal_rfq": "PASS",
            "retry_rehearsal": "WARN",
            "queue_congestion_rehearsal": "PASS",
            "worker_recovery_rehearsal": "PASS",
            "dead_letter_rehearsal": "PASS",
            "rollback_rehearsal": "PASS",
            "telemetry_validation_rehearsal": "PASS",
        },
        {"PASS": 50, "WARN": 1, "FAIL": 0},
    )
    monkeypatch.setattr(rehearsal_mod, "REHEARSAL_RUNTIME_DIR", root)

    service = rehearsal_mod.OperationalRehearsalService()
    readiness = service.readiness_summary()
    history = service.readiness_history()
    latest = service.latest_rehearsal()

    assert readiness["status"] == "ok"
    assert readiness["readiness_score"] >= 70.0
    assert readiness["readiness_grade"] in {"ready", "watch"}
    assert readiness["metrics"]["rehearsal_success_rate"] == 85.71
    assert readiness["metrics"]["retry_recovery_success"] in {60.0, 100.0}
    assert readiness["warning_threshold_indicators"]["operator_intervention_above_threshold"] is False
    assert readiness["trend_summary"]["trend"] in {"stable", "improving", "declining"}
    assert readiness["cadence"]["runs_total"] == 2
    assert readiness["history"][0]["run_id"] == latest_dir.name

    assert history["status"] == "ok"
    assert history["count"] == 2
    assert history["runs"][0]["run_id"] == latest_dir.name

    assert latest["status"] == "ok"
    assert latest["readiness"]["readiness_score"] == readiness["readiness_score"]


def test_operational_rehearsal_service_handles_missing_readiness(tmp_path, monkeypatch) -> None:
    root = tmp_path / "runtime" / "staging" / "rehearsals"
    monkeypatch.setattr(rehearsal_mod, "REHEARSAL_RUNTIME_DIR", root)

    service = rehearsal_mod.OperationalRehearsalService()
    readiness = service.readiness_summary()
    history = service.readiness_history()

    assert readiness["status"] == "not_found"
    assert readiness["readiness_score"] == 0.0
    assert history["count"] == 0
