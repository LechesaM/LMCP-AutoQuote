from __future__ import annotations

import importlib
import json
from pathlib import Path


class _DummyReadinessService:
    def __init__(self, declaration):
        self._declaration = declaration

    def latest_declaration(self):
        return self._declaration


def _write_cycle(root: Path, cycle_id: str, generated_at: str, *, status: str = "PASS", no_go_status: str = "PASS") -> Path:
    cycle_dir = root / cycle_id
    cycle_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "cycle_id": cycle_id,
        "generated_at": generated_at,
        "status": status,
        "summary_counts": {"PASS": 5, "WARN": 0, "FAIL": 0},
        "operator_acknowledgment_required": True,
        "approved_rehearsal_sequence": [
            "operator_review",
            "governance_checkpoint",
            "cadence_verification",
            "readiness_verification",
            "evidence_pack_validation",
        ],
        "operator_acknowledgement": {
            "acknowledged": True,
            "approved_at": "2026-06-23T00:00:00+00:00",
            "approved_rehearsal_sequence": [
                "operator_review",
                "governance_checkpoint",
                "cadence_verification",
                "readiness_verification",
                "evidence_pack_validation",
            ],
            "operator_name": "staging-governance-operator",
            "operator_role": "governance_reviewer",
        },
        "checks": [
            {"name": "operator acknowledgment", "status": "PASS", "message": "Acknowledged", "remediation": "Review"},
            {"name": "governance export verification", "status": "PASS", "message": "Verified", "remediation": "Review"},
            {"name": "evidence pack verification", "status": "PASS", "message": "Verified", "remediation": "Review"},
            {"name": "rehearsal cadence enforcement", "status": "PASS", "message": "Verified", "remediation": "Review"},
            {"name": "concurrency limit enforcement", "status": "PASS", "message": "Verified", "remediation": "Review"},
        ],
        "governance_export": {
            "readiness_summary": {
                "readiness_score": 100.0,
                "readiness_grade": "ready",
                "trend_summary": {"trend": "stable", "delta": 0.0},
                "cadence": {"runs_last_7_days": 2, "average_gap_hours": 6.43, "most_recent_run_at": generated_at, "previous_run_at": "2026-06-23T09:30:20.374101+00:00", "runs_total": 2},
            }
        },
        "evidence_pack": {
            "submission_lock_verification": {"status": "PASS"},
            "dry_run_enforcement_verification": {"status": "PASS"},
            "queue_stability_evidence": {"status": "PASS"},
            "worker_stability_evidence": {"status": "PASS"},
            "telemetry_health_evidence": {"status": "PASS"},
            "retry_recovery_evidence": {"status": "PASS"},
            "rollback_evidence": {"status": "PASS"},
            "operator_intervention_summary": {"status": "PASS"},
            "latest_rehearsal": {
                "timeline": [
                    {"rfq_id": "REHEARSAL-RETRY-001"},
                    {"rfq_id": "REHEARSAL-DLQ-001"},
                ]
            },
        },
        "no_go_condition_summary": {"status": no_go_status, "indicators": [] if no_go_status == "PASS" else ["operator_review_required"]},
        "governance_checkpoint_verified": True,
        "rehearsal_cadence_enforced": True,
        "concurrency_limit_enforced": True,
    }
    (cycle_dir / "pilot_cycle_summary.json").write_text(json.dumps(payload), encoding="utf-8")
    (cycle_dir / "scenario_summary.json").write_text(json.dumps({"rfq_id": "REHEARSAL-RETRY-001"}), encoding="utf-8")
    return cycle_dir


def test_pilot_operator_session_service_reports_active_supervised_sessions(tmp_path) -> None:
    module = importlib.import_module("app.services.pilot_operator_session_service")
    cycle_root = tmp_path / "runtime" / "staging" / "pilot-cycles"
    export_root = tmp_path / "runtime" / "staging" / "governance-exports"
    _write_cycle(cycle_root, "20260623T155559Z-pilot-26adfdf1", "2026-06-23T15:55:59.582013+00:00")
    service = module.PilotOperatorSessionService(cycle_root=cycle_root, export_root=export_root)
    service.readiness = _DummyReadinessService({"status": "ok", "declaration_status": "READY_FOR_CONTROLLED_PILOT", "declaration_grade": "ready", "declaration_score": 96.0})

    latest = service.latest_operator_session()
    history = service.operator_session_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["operator_session_status"] == "ok"
    assert latest["active_operator_session_count"] == 1
    assert latest["operator_session"]["operator_acknowledgement"]["acknowledged"] is True
    assert latest["operator_session"]["supervision_window"]["active"] is True
    assert latest["operator_session"]["readiness_declaration_status"] == "READY_FOR_CONTROLLED_PILOT"
    assert latest["operator_session"]["supervised_rfq_assignments"]
    assert "REHEARSAL-RETRY-001" in {item["rfq_id"] for item in latest["operator_session"]["supervised_rfq_assignments"]}
    assert latest["operator_session"]["escalation_sla_tracking"]["within_sla"] is True
    assert latest["operator_session"]["supervision_coverage"]["approved_sequence_matches"] is True
    assert history["count"] == 1
    assert history["operator_session_history"][0]["operator_session_id"].endswith(":operator-session")


def test_pilot_operator_session_service_warns_on_missing_ack_and_lapsed_window(tmp_path) -> None:
    module = importlib.import_module("app.services.pilot_operator_session_service")
    cycle_root = tmp_path / "runtime" / "staging" / "pilot-cycles"
    export_root = tmp_path / "runtime" / "staging" / "governance-exports"
    _write_cycle(
        cycle_root,
        "20260622T100000Z-pilot-lapsed",
        "2026-06-22T10:00:00+00:00",
        status="WARN",
        no_go_status="WARN",
    )
    (cycle_root / "operator_acknowledgement.json").write_text(json.dumps({"acknowledged": False, "approved_rehearsal_sequence": []}), encoding="utf-8")
    service = module.PilotOperatorSessionService(cycle_root=cycle_root, export_root=export_root)
    service.readiness = _DummyReadinessService({"status": "watch", "declaration_status": "WATCH", "declaration_grade": "watch", "declaration_score": 72.0})

    latest = service.latest_operator_session()

    assert latest["status"] == "blocked"
    assert latest["operator_session_status"] == "blocked"
    assert latest["operator_session"]["operator_acknowledgement"]["acknowledged"] is False
    assert latest["operator_session"]["supervision_window"]["active"] is False
    assert latest["operator_session"]["supervision_lapse_indicators"]["operator_acknowledgement_missing"] is True
    assert latest["operator_session"]["supervision_lapse_indicators"]["supervision_window_closed"] is True
    assert latest["operator_session"]["readiness_declaration_status"] == "WATCH"
    assert latest["warning_indicators"]["unattended_rfq_warning"] is True
