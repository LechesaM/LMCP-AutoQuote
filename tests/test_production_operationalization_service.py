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

    def latest_stability(self):
        return self._response

    def latest_operational_pilot_execution(self):
        return self._response

    def latest_final_readiness(self):
        return self._response


class _DummyExecutiveService:
    def __init__(self, response):
        self._response = response

    def latest_executive_command(self):
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
    }
    (cycle_dir / "pilot_cycle_summary.json").write_text(json.dumps(cycle), encoding="utf-8")
    (pack_dir / "pilot_evidence_pack.json").write_text(json.dumps(pack), encoding="utf-8")
    return cycle_dir


def _ready_service(tmp_path: Path):
    module = importlib.import_module("app.services.production_operationalization_service")
    service = module.ProductionOperationalizationService(
        cycle_root=tmp_path / "runtime" / "staging" / "pilot-cycles",
        evidence_pack_root=tmp_path / "runtime" / "staging" / "evidence-packs",
    )
    items = [
        {
            "rfq_id": "RFQ-PROD-001",
            "tenant_id": "tenant-a",
            "workspace_id": "workspace-a",
            "current_state": "SUBMITTED",
            "submission_method": "portal",
            "submission_status": "submitted",
            "validation_readiness": 96.0,
            "validation_readiness_state": "ready",
            "rfq_lifecycle_duration": 24.0,
        }
    ]
    lifecycle = {
        "generated_at": "2026-06-23T15:55:59+00:00",
        "total_rfqs": 1,
        "queue_trend": {"trend": "stable"},
        "queue_drain_rate": {"overall": 1.3},
        "worker_crash_count": 0,
        "system_health_trend": {"score": 96.0},
    }
    telemetry = {
        "worker_heartbeat": {"status": "healthy"},
        "queue_backlog": {"backlog_detected": False},
        "system_resilience_score": 96.0,
        "worker_crash_count": 0,
        "stalled_lifecycle_tasks": 0,
        "warnings": [],
    }
    review_board = {
        "latest_session": {
            "operator_name": "staging-governance-operator",
            "operator_role": "governance_reviewer",
            "operator_workload": {"pending_approval_items": [], "assigned_rfqs": ["RFQ-PROD-001"]},
        },
        "review_board_cadence": {"runs_last_7_days": 2},
        "outstanding_governance_actions": [],
        "unresolved_operational_exceptions": [],
        "governance_review_history": [{"generated_at": "2026-06-23T15:55:59+00:00"}],
        "review_board_status": "ok",
        "review_board_score": 96.0,
        "institutional_review_summary": {"latest_readiness_score": 96.0},
    }
    stability = {
        "status": "ok",
        "stability_score": 96.0,
        "queue_stability_trend": {"trend": "stable"},
        "worker_stability_trend": {"trend": "stable"},
    }
    final_readiness = {
        "status": "ok",
        "final_submission_readiness_status": "READY_TO_SUBMIT",
        "final_submission_readiness_score": 96.0,
        "latest_final_readiness": {"final_submission_readiness_status": "READY_TO_SUBMIT"},
    }
    execution = {
        "status": "ok",
        "operational_pilot_execution_status": "ok",
        "operational_endurance_score": 95.0,
        "sustained_stability_score": 95.0,
        "latest_operational_pilot_execution": {"operational_pilot_execution_status": "ok"},
    }
    executive = {
        "status": "ok",
        "executive_governance_status": "ok",
        "executive_governance_score": 95.0,
        "latest_executive_intelligence": {"analysis_id": "executive-command:2026-06-23T00:00:00+00:00"},
        "executive_intelligence_history": [
            {
                "analysis_id": "cycle-prod:executive",
                "cycle_id": "cycle-prod",
                "generated_at": "2026-06-23T15:55:59+00:00",
                "executive_governance_score": 95.0,
                "operational_intelligence_score": 95.0,
                "stability_score": 95.0,
                "throughput_score": 95.0,
                "anomaly_score": 95.0,
                "compliance_score": 95.0,
                "supervision_score": 95.0,
                "execution_score": 95.0,
            }
        ],
    }
    service.lifecycle = _DummyLifecycleService(items, lifecycle, telemetry)
    service.executive = _DummyExecutiveService(executive)
    service.review_board = _DummyResponseService(review_board)
    service.stability = _DummyResponseService(stability)
    service.execution = _DummyResponseService(execution)
    service.final_readiness = _DummyResponseService(final_readiness)
    return service


def _warning_service(tmp_path: Path):
    module = importlib.import_module("app.services.production_operationalization_service")
    service = module.ProductionOperationalizationService(
        cycle_root=tmp_path / "runtime" / "staging" / "pilot-cycles",
        evidence_pack_root=tmp_path / "runtime" / "staging" / "evidence-packs",
    )
    items = [
        {
            "rfq_id": "RFQ-PROD-002",
            "tenant_id": "tenant-a",
            "workspace_id": "workspace-b",
            "current_state": "READY_FOR_RETRY",
            "submission_method": "unknown",
            "submission_status": "unknown",
            "validation_readiness": 44.0,
            "validation_readiness_state": "blocked",
            "rfq_lifecycle_duration": 140.0,
        }
    ]
    lifecycle = {
        "generated_at": "2026-06-22T15:55:59+00:00",
        "total_rfqs": 1,
        "queue_trend": {"trend": "declining"},
        "queue_drain_rate": {"overall": 0.2},
        "worker_crash_count": 2,
        "system_health_trend": {"score": 52.0},
    }
    telemetry = {
        "worker_heartbeat": {"status": "degraded"},
        "queue_backlog": {"backlog_detected": True},
        "system_resilience_score": 52.0,
        "worker_crash_count": 2,
        "stalled_lifecycle_tasks": 3,
        "warnings": ["broker_backlog"],
    }
    review_board = {
        "latest_session": {
            "operator_name": "staging-governance-operator",
            "operator_role": "governance_reviewer",
            "operator_workload": {"pending_approval_items": ["RFQ-PROD-002"], "assigned_rfqs": ["RFQ-PROD-002"]},
        },
        "review_board_cadence": {"runs_last_7_days": 0},
        "outstanding_governance_actions": ["review escalated exception"],
        "unresolved_operational_exceptions": ["telemetry"],
        "governance_review_history": [{"generated_at": "2026-06-22T15:55:59+00:00"}],
        "review_board_status": "watch",
        "review_board_score": 52.0,
        "institutional_review_summary": {"latest_readiness_score": 52.0},
    }
    stability = {
        "status": "watch",
        "stability_score": 56.0,
        "queue_stability_trend": {"trend": "declining"},
        "worker_stability_trend": {"trend": "declining"},
    }
    final_readiness = {
        "status": "blocked",
        "final_submission_readiness_status": "NOT_READY_TO_SUBMIT",
        "final_submission_readiness_score": 42.0,
        "latest_final_readiness": {"final_submission_readiness_status": "NOT_READY_TO_SUBMIT"},
    }
    execution = {
        "status": "watch",
        "operational_pilot_execution_status": "watch",
        "operational_endurance_score": 44.0,
        "sustained_stability_score": 40.0,
        "latest_operational_pilot_execution": {"operational_pilot_execution_status": "watch"},
    }
    executive = {
        "status": "watch",
        "executive_governance_status": "watch",
        "executive_governance_score": 62.0,
        "latest_executive_intelligence": {"analysis_id": "executive-command:2026-06-22T00:00:00+00:00"},
        "executive_intelligence_history": [
            {
                "analysis_id": "cycle-warning:executive",
                "cycle_id": "cycle-warning",
                "generated_at": "2026-06-22T15:55:59+00:00",
                "executive_governance_score": 62.0,
                "operational_intelligence_score": 62.0,
                "stability_score": 56.0,
                "throughput_score": 58.0,
                "anomaly_score": 55.0,
                "compliance_score": 60.0,
                "supervision_score": 54.0,
                "execution_score": 50.0,
            }
        ],
    }
    service.lifecycle = _DummyLifecycleService(items, lifecycle, telemetry)
    service.executive = _DummyExecutiveService(executive)
    service.review_board = _DummyResponseService(review_board)
    service.stability = _DummyResponseService(stability)
    service.execution = _DummyResponseService(execution)
    service.final_readiness = _DummyResponseService(final_readiness)
    return service


def test_production_operationalization_service_ready_path(tmp_path: Path) -> None:
    _write_cycle(tmp_path / "runtime" / "staging" / "pilot-cycles", "cycle-ready")
    module = importlib.import_module("app.services.production_operationalization_service")
    service = _ready_service(tmp_path)

    latest = service.latest_production_governance()
    history = service.production_governance_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["production_readiness_status"] == "ok"
    assert latest["production_readiness_score"] >= 85.0
    assert latest["latest_production_governance"]["deployment_readiness_indicators"]["executive_ready"] is True
    assert latest["latest_production_governance"]["recovery_readiness_indicators"]["final_readiness_cleared"] is True
    assert latest["latest_production_governance"]["ha_readiness_indicators"]["queue_stable"] is True
    assert history["count"] >= 1


def test_production_operationalization_service_warning_path(tmp_path: Path) -> None:
    _write_cycle(tmp_path / "runtime" / "staging" / "pilot-cycles", "cycle-warning", generated_at="2026-06-22T15:55:59+00:00")
    service = _warning_service(tmp_path)

    latest = service.latest_production_governance()

    assert latest["status"] in {"watch", "blocked"}
    assert latest["production_readiness_status"] in {"watch", "blocked"}
    assert latest["latest_production_governance"]["deployment_risk_indicators"]["deployment_risk"] is True
    assert latest["latest_production_governance"]["operator_access_risk_indicators"]["pending_approval_backlog"] is True
    assert latest["warnings"]
