from __future__ import annotations

import importlib
import json
from pathlib import Path


class _DummyLifecycleService:
    def __init__(self, items, analytics, telemetry):
        self._items = items
        self._analytics = analytics
        self._telemetry = telemetry

    def analytics(self):
        return self._analytics

    def telemetry(self):
        return self._telemetry

    def list_items(self, state=None, limit=250):
        return {"status": "ok", "count": len(self._items), "items": self._items[:limit]}


class _DummyResponseService:
    def __init__(self, response):
        self._response = response

    def latest_review_board(self):
        return self._response

    def latest_operations_summary(self):
        return self._response

    def latest_stability(self):
        return self._response

    def latest_operational_pilot_execution(self):
        return self._response

    def latest_final_readiness(self):
        return self._response


def _write_cycle(root: Path, cycle_id: str, *, generated_at: str = "2026-06-23T15:55:59+00:00") -> Path:
    cycle_dir = root / cycle_id
    pack_id = f"{cycle_id}-pack"
    pack_dir = root.parent / "evidence-packs" / pack_id
    cycle_dir.mkdir(parents=True, exist_ok=True)
    pack_dir.mkdir(parents=True, exist_ok=True)

    cycle = {
        "cycle_id": cycle_id,
        "generated_at": generated_at,
        "status": "PASS",
        "approved_rehearsal_sequence": ["operator_review", "governance_checkpoint"],
        "checks": [{"status": "PASS"} for _ in range(3)],
        "operator_acknowledgement": {"acknowledged": True},
        "operator_acknowledgment_required": True,
        "rehearsal_cadence_enforced": True,
        "concurrency_limit_enforced": True,
        "evidence_pack": {"pack_id": pack_id, "generated_at": generated_at},
        "governance_export": {
            "readiness_summary": {
                "readiness_score": 95.0,
                "readiness_grade": "ready",
                "trend_summary": {"trend": "stable", "delta": 0.0},
                "cadence": {"runs_last_7_days": 2, "average_gap_hours": 12.0},
            }
        },
    }
    pack = {
        "pack_id": pack_id,
        "generated_at": generated_at,
        "summary_counts": {"PASS": 8, "WARN": 0, "FAIL": 0},
        "readiness_summary": {
            "readiness_score": 95.0,
            "readiness_grade": "ready",
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
        "latest_rehearsal": {"metrics": {"queue_stability": 96.0, "worker_stability": 96.0, "telemetry_health": 96.0, "retry_recovery_success": 95.0, "dlq_escalation_frequency": 0.0, "operator_intervention_frequency": 0.0}},
    }
    (cycle_dir / "pilot_cycle_summary.json").write_text(json.dumps(cycle), encoding="utf-8")
    (pack_dir / "pilot_evidence_pack.json").write_text(json.dumps(pack), encoding="utf-8")
    return cycle_dir


def _ready_service(tmp_path: Path):
    module = importlib.import_module("app.services.operational_intelligence_service")
    service = module.OperationalIntelligenceService(
        cycle_root=tmp_path / "runtime" / "staging" / "pilot-cycles",
        evidence_pack_root=tmp_path / "runtime" / "staging" / "evidence-packs",
    )

    items = [
        {
            "rfq_id": "RFQ-INT-001",
            "title": "Operational intelligence RFQ",
            "current_state": "SUBMITTED",
            "submission_method": "portal",
            "submission_status": "submitted",
            "validation_readiness": 96.0,
            "validation_readiness_state": "ready",
            "failure_classification": "none",
            "primary_blocker": "none",
            "rfq_lifecycle_duration": 24.0,
            "queue_wait_minutes": 12.0,
            "submission_pack": {"ready": True},
            "validation_reason_codes": [],
            "blocker_summary": [],
        }
    ]
    lifecycle = {
        "generated_at": "2026-06-23T15:55:59+00:00",
        "total_rfqs": 1,
        "queue_trend": {"trend": "stable", "delta": 0.0},
        "queue_wait_times": {"ingestion": 12.0, "validation": 14.0},
        "queue_drain_rate": {"overall": 1.4},
        "slowest_stages": ["validation"],
        "worker_crash_count": 0,
    }
    telemetry = {"worker_crash_count": 0, "stalled_lifecycle_tasks": 0, "warnings": [], "system_resilience_score": 96.0}
    review_board = {
        "latest_session": {
            "operator_role": "governance_reviewer",
            "operator_workload": {"pending_approval_items": [], "assigned_rfqs": ["RFQ-INT-001"]},
        },
        "review_board_cadence": {"runs_last_7_days": 2},
        "outstanding_governance_actions": [],
        "unresolved_operational_exceptions": [],
        "governance_review_history": [{"generated_at": "2026-06-23T15:55:59+00:00"}],
    }
    operations = {
        "status": "ok",
        "operations_summary_status": "ok",
        "summary_components": {"readiness": 96.0, "queue": 95.0},
        "consolidated_watch_indicators": {},
        "unresolved_blocker_summary": {},
        "governance_recommendation_summary": {"decision": "support_supervised_pilot"},
        "institutional_operational_summary_history": [{"generated_at": "2026-06-23T15:55:59+00:00"}],
        "warnings": [],
    }
    stability = {
        "status": "ok",
        "stability_score": 96.0,
        "readiness_drift": {"trend": "stable", "score": 96.0},
        "cadence_drift": {"trend": "stable", "score": 96.0},
        "queue_stability_trend": {"trend": "stable", "score": 96.0},
        "worker_stability_trend": {"trend": "stable", "score": 96.0},
        "telemetry_degradation": {"trend": "stable", "score": 96.0},
        "retry_escalation_trend": {"trend": "stable", "score": 96.0},
        "dlq_frequency_trend": {"trend": "stable", "score": 96.0},
        "operator_intervention_trend": {"trend": "stable", "score": 96.0},
        "cadence_compliance": {"status": "ok"},
        "warning_indicators": {},
        "drift_warnings": [],
        "latest_cycle": {"cycle_id": "cycle-ready"},
        "latest_governance_export": {"pack_id": "cycle-ready-pack"},
        "cycles": [{"cycle_id": "cycle-ready"}],
    }
    final_readiness = {
        "status": "ok",
        "final_submission_readiness_status": "READY_TO_SUBMIT",
        "final_submission_readiness_score": 96.0,
        "latest_final_readiness": {
            "final_completeness_verification": {"final_completeness_ok": True},
            "final_compliance_verification": {"final_compliance_ok": True},
            "final_packaging_verification": {"final_packaging_ok": True},
            "final_timing_verification": {"final_timing_ok": True},
            "final_supervision_verification": {"supervision_ok": True},
            "final_modality_verification": {"final_modality_ok": True},
            "governance_override_indicators": {"final_override_required": False},
            "unresolved_blocker_indicators": {"final_completeness_blocker": False},
            "final_escalation_authority": "operator_session",
        },
        "final_readiness_history": [{"final_readiness_id": "RFQ-INT-001:final-readiness"}],
        "final_readiness_rationale_history": [{"final_readiness_id": "RFQ-INT-001:final-readiness"}],
        "warnings": [],
    }
    execution = {
        "status": "ok",
        "operational_pilot_execution_status": "ok",
        "operational_endurance_score": 95.0,
        "sustained_stability_score": 95.0,
        "latest_operational_pilot_execution": {
            "supervised_execution_reliability_indicators": {"operator_acknowledged": True},
            "operational_degradation_indicators": {"queue_degradation": False, "no_go_degradation": False},
        },
        "execution_governance_history": [{"cycle_id": "cycle-ready"}],
        "operational_pilot_execution_history_summary": {"cycle_count": 1},
        "operational_review_intervals": {"queue": {"trend": "stable"}},
        "warnings": [],
    }

    service.lifecycle = _DummyLifecycleService(items, lifecycle, telemetry)
    service.review_board = _DummyResponseService(review_board)
    service.operations_summary = _DummyResponseService(operations)
    service.stability = _DummyResponseService(stability)
    service.final_readiness = _DummyResponseService(final_readiness)
    service.execution = _DummyResponseService(execution)
    service.execution._cycles = lambda: [_write_cycle(tmp_path / "runtime" / "staging" / "pilot-cycles", "cycle-ready")]
    return service


def _warning_service(tmp_path: Path):
    module = importlib.import_module("app.services.operational_intelligence_service")
    service = module.OperationalIntelligenceService(
        cycle_root=tmp_path / "runtime" / "staging" / "pilot-cycles",
        evidence_pack_root=tmp_path / "runtime" / "staging" / "evidence-packs",
    )

    items = [
        {
            "rfq_id": "RFQ-INT-002",
            "title": "Operational intelligence warning RFQ",
            "current_state": "READY_FOR_RETRY",
            "submission_method": "mystery channel",
            "submission_status": "unknown",
            "validation_readiness": 48.0,
            "validation_readiness_state": "blocked",
            "failure_classification": "retry_exhaustion",
            "primary_blocker": "telemetry",
            "rfq_lifecycle_duration": 140.0,
            "queue_wait_minutes": 75.0,
            "submission_pack": {"ready": False},
            "validation_reason_codes": ["missing_artifact"],
            "blocker_summary": ["telemetry"],
        }
    ]
    lifecycle = {
        "generated_at": "2026-06-23T15:55:59+00:00",
        "total_rfqs": 1,
        "queue_trend": {"trend": "declining", "delta": -5.0},
        "queue_wait_times": {"ingestion": 120.0, "validation": 150.0},
        "queue_drain_rate": {"overall": 0.1},
        "slowest_stages": ["validation", "packaging", "submission", "modality"],
        "worker_crash_count": 2,
    }
    telemetry = {"worker_crash_count": 2, "stalled_lifecycle_tasks": 3, "warnings": ["broker_backlog"], "system_resilience_score": 52.0}
    review_board = {
        "latest_session": {
            "operator_role": "governance_reviewer",
            "operator_workload": {"pending_approval_items": ["RFQ-INT-002"], "assigned_rfqs": ["RFQ-INT-002"]},
        },
        "review_board_cadence": {"runs_last_7_days": 0},
        "outstanding_governance_actions": ["review escalated exception"],
        "unresolved_operational_exceptions": ["telemetry"],
        "governance_review_history": [{"generated_at": "2026-06-23T15:55:59+00:00"}],
    }
    operations = {
        "status": "watch",
        "operations_summary_status": "watch",
        "summary_components": {"readiness": 48.0, "queue": 42.0},
        "consolidated_watch_indicators": {"queue_pressure": True},
        "unresolved_blocker_summary": {"telemetry": True},
        "governance_recommendation_summary": {"decision": "defer_supervised_pilot"},
        "institutional_operational_summary_history": [{"generated_at": "2026-06-23T15:55:59+00:00"}],
        "warnings": ["queue pressure"],
    }
    stability = {
        "status": "watch",
        "stability_score": 56.0,
        "readiness_drift": {"trend": "declining", "score": 56.0},
        "cadence_drift": {"trend": "declining", "score": 56.0},
        "queue_stability_trend": {"trend": "declining", "score": 42.0},
        "worker_stability_trend": {"trend": "declining", "score": 40.0},
        "telemetry_degradation": {"trend": "declining", "score": 35.0},
        "retry_escalation_trend": {"trend": "declining", "score": 30.0},
        "dlq_frequency_trend": {"trend": "declining", "score": 28.0},
        "operator_intervention_trend": {"trend": "declining", "score": 25.0},
        "cadence_compliance": {"status": "watch"},
        "warning_indicators": {"missed_review": True},
        "drift_warnings": ["readiness_drift_warning", "queue_stability_warning"],
        "latest_cycle": {"cycle_id": "cycle-warning"},
        "latest_governance_export": {"pack_id": "cycle-warning-pack"},
        "cycles": [{"cycle_id": "cycle-warning"}],
    }
    final_readiness = {
        "status": "blocked",
        "final_submission_readiness_status": "NOT_READY_TO_SUBMIT",
        "final_submission_readiness_score": 42.0,
        "latest_final_readiness": {
            "final_completeness_verification": {"final_completeness_ok": False},
            "final_compliance_verification": {"final_compliance_ok": False},
            "final_packaging_verification": {"final_packaging_ok": False},
            "final_timing_verification": {"final_timing_ok": False},
            "final_supervision_verification": {"supervision_ok": False},
            "final_modality_verification": {"final_modality_ok": False},
            "governance_override_indicators": {"final_override_required": True},
            "unresolved_blocker_indicators": {"final_completeness_blocker": True},
            "final_escalation_authority": "governance_review_board",
        },
        "final_readiness_history": [{"final_readiness_id": "RFQ-INT-002:final-readiness"}],
        "final_readiness_rationale_history": [{"final_readiness_id": "RFQ-INT-002:final-readiness"}],
        "warnings": ["final readiness blocked"],
    }
    execution = {
        "status": "watch",
        "operational_pilot_execution_status": "watch",
        "operational_endurance_score": 44.0,
        "sustained_stability_score": 40.0,
        "latest_operational_pilot_execution": {
            "supervised_execution_reliability_indicators": {"operator_acknowledged": False},
            "operational_degradation_indicators": {"queue_degradation": True, "no_go_degradation": True},
        },
        "execution_governance_history": [{"cycle_id": "cycle-warning"}],
        "operational_pilot_execution_history_summary": {"cycle_count": 1},
        "operational_review_intervals": {"queue": {"trend": "declining"}},
        "warnings": ["execution degraded"],
    }

    service.lifecycle = _DummyLifecycleService(items, lifecycle, telemetry)
    service.review_board = _DummyResponseService(review_board)
    service.operations_summary = _DummyResponseService(operations)
    service.stability = _DummyResponseService(stability)
    service.final_readiness = _DummyResponseService(final_readiness)
    service.execution = _DummyResponseService(execution)
    service.execution._cycles = lambda: [_write_cycle(tmp_path / "runtime" / "staging" / "pilot-cycles", "cycle-warning", generated_at="2026-06-22T15:55:59+00:00")]
    return service


def test_operational_intelligence_service_ready_path(tmp_path: Path) -> None:
    service = _ready_service(tmp_path)

    latest = service.latest_operational_intelligence()
    history = service.operational_intelligence_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["operational_intelligence_status"] == "ok"
    assert latest["operational_intelligence_score"] >= 85.0
    assert latest["latest_operational_intelligence"]["governance_degradation_indicators"]["final_readiness_warning"] is False
    assert latest["latest_operational_intelligence"]["supervision_saturation_indicators"]["saturation_warning"] is False
    assert latest["latest_operational_intelligence"]["operational_intelligence_decision"] == "support_supervised_pilot"
    assert history["count"] >= 1


def test_operational_intelligence_service_warning_path(tmp_path: Path) -> None:
    service = _warning_service(tmp_path)

    latest = service.latest_operational_intelligence()

    assert latest["status"] in {"watch", "blocked"}
    assert latest["operational_intelligence_status"] in {"watch", "blocked"}
    assert latest["latest_operational_intelligence"]["governance_degradation_indicators"]["final_readiness_warning"] is True
    assert latest["latest_operational_intelligence"]["supervision_saturation_indicators"]["saturation_warning"] is True
    assert latest["warnings"]
