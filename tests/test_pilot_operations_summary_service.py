from __future__ import annotations

import importlib
import json
from pathlib import Path


def _write_cycle(root: Path, cycle_id: str, generated_at: str, *, readiness_score: float = 100.0, no_go_status: str = "PASS") -> None:
    cycle_dir = root / cycle_id
    cycle_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "cycle_id": cycle_id,
        "generated_at": generated_at,
        "summary_counts": {"PASS": 5, "WARN": 0, "FAIL": 0},
        "governance_checkpoint_verified": True,
        "rehearsal_cadence_enforced": True,
        "concurrency_limit_enforced": True,
        "no_go_condition_summary": {"status": no_go_status, "indicators": [] if no_go_status == "PASS" else ["operator_review_required"]},
        "checks": [
            {"name": "Operator acknowledgment", "message": "Operator acknowledgment is present and matches the approved rehearsal sequence.", "remediation": "Create a valid staging operator acknowledgement artifact in runtime/staging/pilot-cycles/operator_acknowledgement.json.", "status": "PASS"},
            {"name": "Governance export verification", "message": "Latest governance export satisfies readiness, no-go, submission-lock, and dry-run checks.", "remediation": "Regenerate the governance export until readiness, no-go, submission-lock, and dry-run checks all pass.", "status": "PASS"},
            {"name": "Latest evidence pack verification", "message": "Latest evidence pack is present and aligns with the approved readiness posture.", "remediation": "Regenerate the pilot evidence pack so the latest pack is present and ready.", "status": "PASS"},
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
            "queue_stability_evidence": {"status": "PASS", "notes": ["Queue evidence"]},
            "worker_stability_evidence": {"status": "PASS", "notes": ["Worker evidence"]},
            "telemetry_health_evidence": {"status": "PASS", "notes": ["Telemetry evidence"]},
            "retry_recovery_evidence": {"status": "PASS", "notes": ["Retry evidence"]},
            "rollback_evidence": {"status": "PASS", "notes": ["Rollback evidence"]},
            "operator_intervention_summary": {"status": "PASS", "notes": ["Operator evidence"]},
            "submission_lock_verification": {"status": "PASS", "notes": ["Submission lock evidence"]},
            "dry_run_enforcement_verification": {"status": "PASS", "notes": ["Dry-run evidence"]},
            "artifact_summary": {"artifact_count": 18, "total_size_bytes": 451294},
            "latest_rehearsal": {"metrics": {"operator_intervention_frequency": 0.0}, "timeline": [{"scenario": "normal_rfq", "index": 1}]},
        },
    }
    (cycle_dir / "pilot_cycle_summary.json").write_text(json.dumps(payload), encoding="utf-8")


def test_pilot_operations_summary_service_combines_governance_surfaces(tmp_path) -> None:
    module = importlib.import_module("app.services.pilot_operations_summary_service")
    cycle_root = tmp_path / "runtime" / "staging" / "pilot-cycles"
    export_root = tmp_path / "runtime" / "staging" / "governance-exports"
    _write_cycle(cycle_root, "cycle-1", "2026-06-23T11:30:52+00:00", readiness_score=98.0)
    export_dir = export_root / "export-1"
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "pilot_rehearsal_summary.json").write_text(json.dumps({
        "export_id": "export-1",
        "generated_at": "2026-06-23T11:09:09+00:00",
        "summary_counts": {"PASS": 5, "WARN": 0, "FAIL": 0},
        "readiness_summary": {"readiness_score": 98.0, "readiness_grade": "ready"},
        "submission_lock_verification": {"status": "PASS"},
        "dry_run_enforcement_verification": {"status": "PASS"},
        "no_go_condition_summary": {"status": "PASS", "indicators": []},
        "governance_review_section": {"items": [], "guidance": ["Continue controlled staging operations."], "status": "PASS"},
        "operator_sign_off_section": {"items": [], "guidance": ["Operator acknowledgement remains current."], "status": "PASS"},
        "latest_evidence_pack": {"pack_id": "pack-1"},
    }), encoding="utf-8")

    service = module.PilotOperationsSummaryService(cycle_root=cycle_root, export_root=export_root)
    latest = service.latest_operations_summary()
    history = service.operations_summary_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["consolidated_governance_score"] >= 85.0
    assert latest["readiness_status"] == "ok"
    assert latest["stability_status"] == "ok"
    assert latest["remediation_status"] == "ok"
    assert latest["progression_status"] in {"ok", "watch"}
    assert latest["governance_review_status"] == "ok"
    assert history["count"] >= 1
    assert history["institutional_operational_summary_history"]


def test_pilot_operations_summary_service_warns_on_open_governance_risks(tmp_path) -> None:
    module = importlib.import_module("app.services.pilot_operations_summary_service")
    cycle_root = tmp_path / "runtime" / "staging" / "pilot-cycles"
    export_root = tmp_path / "runtime" / "staging" / "governance-exports"
    _write_cycle(cycle_root, "cycle-open", "2026-06-20T11:30:52+00:00", readiness_score=68.0, no_go_status="WARN")
    export_dir = export_root / "export-1"
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "pilot_rehearsal_summary.json").write_text(json.dumps({
        "export_id": "export-1",
        "generated_at": "2026-06-20T11:09:09+00:00",
        "summary_counts": {"PASS": 4, "WARN": 1, "FAIL": 0},
        "readiness_summary": {"readiness_score": 68.0, "readiness_grade": "watch"},
        "submission_lock_verification": {"status": "WARN"},
        "dry_run_enforcement_verification": {"status": "WARN"},
        "no_go_condition_summary": {"status": "WARN", "indicators": ["operator_review_required"]},
        "governance_review_section": {"items": [{"item": "review", "status": "WARN"}], "guidance": ["Review required."], "status": "WARN"},
        "operator_sign_off_section": {"items": [{"item": "ack", "status": "WARN"}], "guidance": ["Ack missing."], "status": "WARN"},
        "latest_evidence_pack": {"pack_id": "pack-1"},
    }), encoding="utf-8")

    service = module.PilotOperationsSummaryService(cycle_root=cycle_root, export_root=export_root)
    latest = service.latest_operations_summary()

    assert latest["status"] == "blocked"
    assert latest["consolidated_governance_score"] < 85.0
    assert latest["consolidated_watch_indicators"]["no_go_watch"] is True
    assert latest["consolidated_watch_indicators"]["readiness_watch"] is True
    assert latest["warning_indicators"]["no_go_warning"] is True
