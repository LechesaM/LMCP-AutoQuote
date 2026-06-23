from __future__ import annotations

import importlib
import json
from pathlib import Path


class _DummyRehearsalService:
    def readiness_summary(self, limit: int = 20):
        return {
            "status": "ok",
            "readiness_score": 100.0,
            "readiness_grade": "ready",
            "metrics": {"queue_stability": 100.0, "worker_stability": 100.0, "telemetry_health": 100.0, "retry_recovery_success": 100.0, "dlq_escalation_frequency": 0.0, "operator_intervention_frequency": 0.0},
            "warning_threshold_indicators": {},
            "thresholds": {"readiness_score": 85.0},
            "trend_summary": {"trend": "stable", "delta": 0.0},
            "cadence": {"runs_last_7_days": 1, "average_gap_hours": 24.0},
        }

    def readiness_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "runs": [
                {
                    "run_id": "rehearsal-1",
                    "generated_at": "2026-06-23T00:00:00+00:00",
                    "readiness_score": 100.0,
                    "metrics": {"queue_stability": 100.0, "worker_stability": 100.0, "telemetry_health": 100.0, "retry_recovery_success": 100.0, "dlq_escalation_frequency": 0.0, "operator_intervention_frequency": 0.0},
                }
            ],
            "trend_summary": {"trend": "stable"},
            "cadence": {"runs_last_7_days": 1},
        }


def _write_cycle(root: Path, cycle_id: str, readiness_score: float, queue_status: str, worker_status: str, telemetry_status: str, retry_status: str) -> None:
    cycle_dir = root / cycle_id
    cycle_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "cycle_id": cycle_id,
        "generated_at": "2026-06-23T00:00:00+00:00",
        "governance_export": {
            "readiness_summary": {
                "readiness_score": readiness_score,
                "readiness_grade": "ready" if readiness_score >= 85 else "watch",
                "thresholds": {"readiness_score": 85.0},
                "trend_summary": {"trend": "stable", "delta": 0.0},
                "cadence": {"runs_last_7_days": 1},
            }
        },
        "evidence_pack": {
            "queue_stability_evidence": {"status": queue_status},
            "worker_stability_evidence": {"status": worker_status},
            "telemetry_health_evidence": {"status": telemetry_status},
            "retry_recovery_evidence": {"status": retry_status},
            "rollback_evidence": {"status": "PASS"},
            "operator_intervention_summary": {"status": "PASS"},
            "submission_lock_verification": {"status": "PASS"},
            "dry_run_enforcement_verification": {"status": "PASS"},
        },
        "metrics": {"readiness_score": readiness_score},
        "summary_counts": {"PASS": 5, "WARN": 0, "FAIL": 0},
    }
    (cycle_dir / "pilot_cycle_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_export(root: Path, export_id: str, readiness_score: float, trend: str = "stable") -> None:
    export_dir = root / export_id
    export_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "export_id": export_id,
        "generated_at": "2026-06-23T00:00:00+00:00",
        "readiness_summary": {
            "readiness_score": readiness_score,
            "readiness_grade": "ready" if readiness_score >= 85 else "watch",
            "trend_summary": {"trend": trend, "delta": 0.0},
            "cadence": {"runs_last_7_days": 1},
            "thresholds": {"readiness_score": 85.0},
            "warning_threshold_indicators": {},
        },
        "rehearsal_history_summary": {"count": 1, "runs": [{"run_id": "rehearsal-1"}], "trend_summary": {"trend": trend}, "cadence": {"runs_last_7_days": 1}},
        "PASS/WARN/FAIL_trends": {"summary": {"PASS": 10, "WARN": 0, "FAIL": 0}},
        "queue_stability_summary": {"status": "PASS"},
        "rollback_evidence_summary": {"status": "PASS"},
        "telemetry_health_summary": {"status": "PASS"},
        "submission_lock_verification": {"status": "PASS"},
        "dry_run_enforcement_verification": {"status": "PASS"},
        "no_go_condition_summary": {"status": "PASS", "indicators": []},
        "pilot_authorization_recommendation": "authorise_pilot",
    }
    (export_dir / "pilot_rehearsal_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_operational_stability_service_tracks_stability_and_drift(monkeypatch, tmp_path) -> None:
    module = importlib.import_module("app.services.operational_stability_service")
    cycle_root = tmp_path / "runtime" / "staging" / "pilot-cycles"
    export_root = tmp_path / "runtime" / "staging" / "governance-exports"
    _write_cycle(cycle_root, "cycle-1", 90.0, "PASS", "PASS", "PASS", "PASS")
    _write_cycle(cycle_root, "cycle-2", 92.0, "PASS", "PASS", "PASS", "PASS")
    _write_export(export_root, "export-1", 90.0, trend="improving")
    _write_export(export_root, "export-2", 92.0, trend="stable")
    monkeypatch.setattr(module, "PILOT_CYCLE_ROOT", cycle_root)
    monkeypatch.setattr(module, "GOVERNANCE_EXPORT_ROOT", export_root)

    service = module.OperationalStabilityService(cycle_root=cycle_root, export_root=export_root)
    service.rehearsal_service = _DummyRehearsalService()
    latest = service.latest_stability()
    history = service.stability_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["stability_score"] >= 85
    assert latest["stability"]["readiness_drift"]["trend"] in {"stable", "improving"}
    assert latest["stability"]["cadence_compliance"]["compliant"] is True
    assert history["count"] >= 1
