from __future__ import annotations

import importlib
import json
from pathlib import Path


def _write_cycle(root: Path, cycle_id: str, generated_at: str, *, readiness_score: float = 100.0, pass_count: int = 10, warn_count: int = 0, fail_count: int = 0, no_go_status: str = "PASS", gov_checkpoint: bool = True, cadence_enforced: bool = True, concurrency_enforced: bool = True, dry_run_status: str = "PASS", lock_status: str = "PASS", artifact_count: int = 18) -> None:
    cycle_dir = root / cycle_id
    cycle_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "cycle_id": cycle_id,
        "generated_at": generated_at,
        "summary_counts": {"PASS": pass_count, "WARN": warn_count, "FAIL": fail_count},
        "governance_checkpoint_verified": gov_checkpoint,
        "rehearsal_cadence_enforced": cadence_enforced,
        "concurrency_limit_enforced": concurrency_enforced,
        "operator_acknowledgement": {"acknowledged": True},
        "no_go_condition_summary": {"status": no_go_status, "indicators": [] if no_go_status == "PASS" else ["operator_review_required"]},
        "governance_export": {
            "readiness_summary": {
                "readiness_score": readiness_score,
                "readiness_grade": "ready" if readiness_score >= 85 else "watch",
                "trend_summary": {"trend": "stable", "delta": 0.0},
                "cadence": {"runs_last_7_days": 1, "average_gap_hours": 0.0, "most_recent_run_at": generated_at, "previous_run_at": "", "runs_total": 1},
            }
        },
        "evidence_pack": {
            "submission_lock_verification": {"status": lock_status},
            "dry_run_enforcement_verification": {"status": dry_run_status},
            "queue_stability_evidence": {"status": "PASS"},
            "worker_stability_evidence": {"status": "PASS"},
            "telemetry_health_evidence": {"status": "PASS"},
            "retry_recovery_evidence": {"status": "PASS"},
            "rollback_evidence": {"status": "PASS"},
            "operator_intervention_summary": {"status": "PASS"},
            "artifact_summary": {"artifact_count": artifact_count, "total_size_bytes": artifact_count * 1000},
            "latest_rehearsal": {"timeline": [{"scenario": "normal_rfq", "index": 1}]},
        },
    }
    (cycle_dir / "pilot_cycle_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_recurring_pilot_cycle_service_reports_longitudinal_history(monkeypatch, tmp_path) -> None:
    module = importlib.import_module("app.services.recurring_pilot_cycle_service")
    cycle_root = tmp_path / "runtime" / "staging" / "pilot-cycles"
    _write_cycle(cycle_root, "cycle-1", "2026-06-01T11:30:52+00:00", readiness_score=92.0)
    _write_cycle(cycle_root, "cycle-2", "2026-06-10T11:30:52+00:00", readiness_score=95.0)
    _write_cycle(cycle_root, "cycle-3", "2026-06-23T11:30:52+00:00", readiness_score=100.0)

    service = module.RecurringPilotCycleService(cycle_root=cycle_root)
    latest = service.latest_recurring_cycles()
    history = service.recurring_cycles_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["recurring_cycle_score"] >= 85
    assert latest["recurring_cycle_status"] == "ok"
    assert latest["latest_cycle"]["cycle_id"] == "cycle-3"
    assert latest["governance_compliance_summary"]["status"] == "PASS"
    assert latest["operational_endurance_indicators"]["clean_cycle_rate"] == 100.0
    assert latest["recurring_stability_snapshots"]
    assert history["count"] == 3
    assert history["cycle_history"][0]["cycle_id"] == "cycle-3"


def test_recurring_pilot_cycle_service_warns_on_stability_and_governance_issues(monkeypatch, tmp_path) -> None:
    module = importlib.import_module("app.services.recurring_pilot_cycle_service")
    cycle_root = tmp_path / "runtime" / "staging" / "pilot-cycles"
    _write_cycle(cycle_root, "cycle-old", "2026-06-01T11:30:52+00:00", readiness_score=82.0, warn_count=2, no_go_status="WARN", gov_checkpoint=False, cadence_enforced=False, concurrency_enforced=False, dry_run_status="WARN", lock_status="WARN", artifact_count=0)

    service = module.RecurringPilotCycleService(cycle_root=cycle_root)
    latest = service.latest_recurring_cycles()

    assert latest["status"] == "watch"
    assert latest["warning_indicators"]["readiness_drift_warning"] is True
    assert latest["warning_indicators"]["governance_compliance_warning"] is True
    assert latest["warning_indicators"]["endurance_warning"] is True
    assert latest["warnings"]
