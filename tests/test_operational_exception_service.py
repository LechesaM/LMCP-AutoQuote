from __future__ import annotations

import importlib
import json
from pathlib import Path


def _write_cycle(root: Path, cycle_id: str, generated_at: str, *, fail_check: bool = False, queue_status: str = "PASS", telemetry_status: str = "PASS", retry_status: str = "PASS", lock_status: str = "PASS", dry_run_status: str = "PASS", no_go_status: str = "PASS", readiness_score: float = 100.0, operator_frequency: float = 0.0) -> None:
    cycle_dir = root / cycle_id
    cycle_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "cycle_id": cycle_id,
        "generated_at": generated_at,
        "summary_counts": {"PASS": 5 if not fail_check else 4, "WARN": 0, "FAIL": 0 if not fail_check else 1},
        "governance_checkpoint_verified": True,
        "rehearsal_cadence_enforced": True,
        "concurrency_limit_enforced": True,
        "no_go_condition_summary": {"status": no_go_status, "indicators": [] if no_go_status == "PASS" else ["operator_review_required"]},
        "checks": [
            {"name": "Operator acknowledgment", "message": "Operator acknowledgment is present and matches the approved rehearsal sequence.", "remediation": "Create a valid staging operator acknowledgement artifact in runtime/staging/pilot-cycles/operator_acknowledgement.json.", "status": "PASS"},
            {"name": "Governance export verification", "message": "Latest governance export satisfies readiness, no-go, submission-lock, and dry-run checks.", "remediation": "Regenerate the governance export until readiness, no-go, submission-lock, and dry-run checks all pass.", "status": "PASS"},
            {"name": "Latest evidence pack verification", "message": "Latest evidence pack is present and aligns with the approved readiness posture.", "remediation": "Regenerate the pilot evidence pack so the latest pack is present and ready.", "status": "FAIL" if fail_check else "PASS"},
            {"name": "Rehearsal cadence enforcement", "message": "Rehearsal cadence is 1 run(s) in the last 7 days.", "remediation": "Run at least one approved staging rehearsal in the last 7 days.", "status": "PASS"},
            {"name": "Concurrency limit enforcement", "message": "Pilot concurrency limit is 1; current cycle executes with a single lock.", "remediation": "Set LMCP_PILOT_MAX_CONCURRENCY=1 for controlled pilot execution.", "status": "PASS"},
        ],
        "governance_export": {
            "readiness_summary": {
                "readiness_score": readiness_score,
                "readiness_grade": "ready" if readiness_score >= 85 else "watch",
                "trend_summary": {"trend": "stable", "delta": 0.0},
                "cadence": {"runs_last_7_days": 1, "average_gap_hours": 0.0, "most_recent_run_at": generated_at, "previous_run_at": "", "runs_total": 1},
                "thresholds": {"readiness_score": 70.0},
            }
        },
        "evidence_pack": {
            "queue_stability_evidence": {"status": queue_status, "notes": ["Queue evidence"]},
            "worker_stability_evidence": {"status": "PASS", "notes": ["Worker evidence"]},
            "telemetry_health_evidence": {"status": telemetry_status, "notes": ["Telemetry evidence"]},
            "retry_recovery_evidence": {"status": retry_status, "notes": ["Retry evidence"]},
            "rollback_evidence": {"status": "PASS", "notes": ["Rollback evidence"]},
            "operator_intervention_summary": {"status": "FAIL" if operator_frequency > 20.0 else "PASS", "notes": ["Operator evidence"]},
            "submission_lock_verification": {"status": lock_status, "notes": ["Submission lock evidence"]},
            "dry_run_enforcement_verification": {"status": dry_run_status, "notes": ["Dry-run evidence"]},
            "artifact_summary": {"artifact_count": 18 if not fail_check else 16, "total_size_bytes": 451294},
            "latest_rehearsal": {"metrics": {"operator_intervention_frequency": operator_frequency}, "timeline": [{"scenario": "normal_rfq", "index": 1}]},
        },
    }
    (cycle_dir / "pilot_cycle_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_operational_exception_service_reports_resolved_transient_failures(monkeypatch, tmp_path) -> None:
    module = importlib.import_module("app.services.operational_exception_service")
    cycle_root = tmp_path / "runtime" / "staging" / "pilot-cycles"
    export_root = tmp_path / "runtime" / "staging" / "governance-exports"
    _write_cycle(cycle_root, "cycle-1", "2026-06-01T11:30:52+00:00", fail_check=True)
    _write_cycle(cycle_root, "cycle-2", "2026-06-10T11:30:52+00:00", fail_check=True)
    _write_cycle(cycle_root, "cycle-3", "2026-06-23T11:30:52+00:00", fail_check=False)
    export_dir = export_root / "export-1"
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "pilot_rehearsal_summary.json").write_text(json.dumps({"export_id": "export-1", "generated_at": "2026-06-23T11:09:09+00:00", "readiness_summary": {"readiness_score": 100.0, "readiness_grade": "ready"}}), encoding="utf-8")

    service = module.OperationalExceptionService(cycle_root=cycle_root, export_root=export_root)
    latest = service.latest_exceptions()
    history = service.exceptions_history(limit=5)

    assert latest["status"] == "watch"
    assert latest["exception_summary"]["transient_failure_count"] == 2
    assert latest["exception_summary"]["open_exception_count"] == 0
    assert latest["exception_summary"]["resolved_exception_count"] == 2
    assert latest["operational_risk_indicators"]["repeated_exception_types"] == ["transient_failure"]
    assert latest["remediation_status_summary"]["resolved_count"] == 2
    assert history["count"] == 2


def test_operational_exception_service_tracks_unresolved_governance_and_telemetry_failures(monkeypatch, tmp_path) -> None:
    module = importlib.import_module("app.services.operational_exception_service")
    cycle_root = tmp_path / "runtime" / "staging" / "pilot-cycles"
    export_root = tmp_path / "runtime" / "staging" / "governance-exports"
    _write_cycle(
        cycle_root,
        "cycle-open",
        "2026-06-23T11:30:52+00:00",
        fail_check=False,
        queue_status="FAIL",
        telemetry_status="FAIL",
        retry_status="FAIL",
        lock_status="WARN",
        dry_run_status="WARN",
        no_go_status="WARN",
        readiness_score=68.0,
        operator_frequency=30.0,
    )
    export_dir = export_root / "export-1"
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "pilot_rehearsal_summary.json").write_text(json.dumps({"export_id": "export-1", "generated_at": "2026-06-23T11:09:09+00:00", "readiness_summary": {"readiness_score": 68.0, "readiness_grade": "watch"}}), encoding="utf-8")

    service = module.OperationalExceptionService(cycle_root=cycle_root, export_root=export_root)
    latest = service.latest_exceptions()

    assert latest["status"] == "watch"
    assert latest["exception_summary"]["queue_instability_count"] == 1
    assert latest["exception_summary"]["telemetry_degradation_count"] == 1
    assert latest["exception_summary"]["retry_exhaustion_count"] == 1
    assert latest["exception_summary"]["governance_compliance_failure_count"] >= 1
    assert latest["exception_summary"]["operator_intervention_anomaly_count"] == 1
    assert latest["unresolved_exception_tracking"]
    assert latest["operational_risk_indicators"]["queue_instability_risk"] is True
    assert latest["operational_risk_indicators"]["telemetry_degradation_risk"] is True
    assert latest["operational_risk_indicators"]["retry_exhaustion_risk"] is True
