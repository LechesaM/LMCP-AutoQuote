from __future__ import annotations

import importlib
import json
from pathlib import Path


def _write_cycle(root: Path, cycle_id: str, *, status: str = "PASS", readiness_score: float = 96.0, warn: bool = False) -> Path:
    cycle_dir = root / cycle_id
    pack_id = f"{cycle_id}-pack"
    pack_dir = root.parent / "evidence-packs" / pack_id
    cycle_dir.mkdir(parents=True, exist_ok=True)
    pack_dir.mkdir(parents=True, exist_ok=True)

    pack = {
        "pack_id": pack_id,
        "generated_at": "2026-06-23T15:55:59+00:00",
        "summary_counts": {"PASS": 10, "WARN": 0 if not warn else 1, "FAIL": 0},
        "readiness_summary": {
            "readiness_score": readiness_score,
            "readiness_grade": "ready" if readiness_score >= 85 else "watch",
            "trend_summary": {"trend": "stable", "delta": 0.0},
            "cadence": {"runs_last_7_days": 2, "average_gap_hours": 12.0},
        },
        "queue_stability_evidence": {"status": "PASS"},
        "worker_stability_evidence": {"status": "PASS"},
        "telemetry_health_evidence": {"status": "PASS"},
        "retry_recovery_evidence": {"status": "PASS"},
        "rollback_evidence": {"status": "PASS"},
        "operator_intervention_summary": {"status": "PASS"},
        "submission_lock_verification": {"status": "PASS"},
        "dry_run_enforcement_verification": {"status": "PASS"},
        "artifact_paths": {"json": "pilot_evidence_pack.json", "markdown": "pilot_evidence_pack.md"},
        "latest_rehearsal": {"metrics": {"queue_stability": 95.0, "worker_stability": 96.0, "telemetry_health": 95.0, "retry_recovery_success": 95.0, "dlq_escalation_frequency": 0.0, "operator_intervention_frequency": 0.0}},
    }
    cycle = {
        "approved_rehearsal_sequence": ["operator_review", "governance_checkpoint"],
        "checks": [{"status": "PASS"} for _ in range(5)],
        "concurrency_limit_enforced": True,
        "cycle_id": cycle_id,
        "evidence_pack": {
            "pack_id": pack_id,
            "generated_at": pack["generated_at"],
            "summary_counts": pack["summary_counts"],
            "readiness_summary": pack["readiness_summary"],
            "latest_rehearsal": pack["latest_rehearsal"],
        },
        "generated_at": "2026-06-23T15:55:59+00:00",
        "governance_checkpoint_verified": True,
        "governance_export": {
            "readiness_summary": {
                "readiness_score": readiness_score,
                "readiness_grade": "ready" if readiness_score >= 85 else "watch",
                "trend_summary": {"trend": "stable", "delta": 0.0},
                "cadence": {"runs_last_7_days": 2, "average_gap_hours": 12.0, "most_recent_run_at": "2026-06-23T15:55:59+00:00", "previous_run_at": "2026-06-22T15:55:59+00:00"},
            }
        },
        "metrics": {"readiness_score": readiness_score, "rehearsal_runs_last_7_days": 2, "rehearsal_average_gap_hours": 12.0},
        "no_go_condition_summary": {"status": status, "indicators": [] if status == "PASS" else ["recent_no_go_history"]},
        "operator_acknowledgement": {"acknowledged": True},
        "operator_acknowledgment_required": True,
        "rehearsal_cadence_enforced": True,
        "safety_guarantees": {"dry_run": True},
        "source_paths": {},
        "status": status,
        "summary_counts": {"PASS": 5, "WARN": 0 if not warn else 1, "FAIL": 0},
        "telemetry_events": [],
    }
    (cycle_dir / "pilot_cycle_summary.json").write_text(json.dumps(cycle), encoding="utf-8")
    (pack_dir / "pilot_evidence_pack.json").write_text(json.dumps(pack), encoding="utf-8")
    return cycle_dir


def test_operational_pilot_execution_service_ready_path(tmp_path) -> None:
    module = importlib.import_module("app.services.operational_pilot_execution_service")
    service = module.OperationalPilotExecutionService(
        cycle_root=tmp_path / "runtime" / "staging" / "pilot-cycles",
        evidence_pack_root=tmp_path / "runtime" / "staging" / "evidence-packs",
    )
    _write_cycle(tmp_path / "runtime" / "staging" / "pilot-cycles", "cycle-ready")

    latest = service.latest_operational_pilot_execution()
    history = service.operational_pilot_execution_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["operational_pilot_execution_status"] == "ok"
    assert latest["operational_endurance_score"] >= 90.0
    assert latest["sustained_stability_score"] >= 90.0
    assert latest["latest_operational_pilot_execution"]["supervised_execution_reliability_indicators"]["operator_acknowledged"] is True
    assert latest["latest_operational_pilot_execution"]["operational_degradation_indicators"]["queue_degradation"] is False
    assert history["count"] >= 1


def test_operational_pilot_execution_service_warn_path(tmp_path) -> None:
    module = importlib.import_module("app.services.operational_pilot_execution_service")
    service = module.OperationalPilotExecutionService(
        cycle_root=tmp_path / "runtime" / "staging" / "pilot-cycles",
        evidence_pack_root=tmp_path / "runtime" / "staging" / "evidence-packs",
    )
    _write_cycle(tmp_path / "runtime" / "staging" / "pilot-cycles", "cycle-warn", status="WARN", readiness_score=72.0, warn=True)

    latest = service.latest_operational_pilot_execution()

    assert latest["status"] in {"watch", "blocked"}
    assert latest["operational_pilot_execution_status"] in {"watch", "blocked"}
    assert latest["latest_operational_pilot_execution"]["operational_degradation_indicators"]["no_go_degradation"] is True
    assert latest["warnings"]
