from __future__ import annotations

import importlib


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


class _DummyIntelligenceService:
    def __init__(self, response):
        self._response = response

    def latest_operational_intelligence(self):
        return self._response


def _ready_payload():
    return {
        "status": "ok",
        "operational_intelligence_status": "ok",
        "operational_intelligence_score": 95.0,
        "latest_operational_intelligence": {"analysis_id": "lifecycle:intelligence:2026-06-23T00:00:00+00:00"},
        "operational_intelligence_history": [
            {
                "analysis_id": "cycle-ready:intelligence",
                "cycle_id": "cycle-ready",
                "generated_at": "2026-06-23T00:00:00+00:00",
                "operational_intelligence_score": 95.0,
                "warnings": [],
                "throughput_score": 94.0,
                "anomaly_score": 95.0,
                "compliance_score": 96.0,
                "supervision_score": 95.0,
                "execution_score": 95.0,
                "stability_score": 95.0,
                "operational_intelligence_decision": "support_supervised_pilot",
                "rfq_trend_score": 95.0,
            }
        ],
        "operational_intelligence_history_summary": {"analysis_count": 1},
        "summary_components": {"rfq_trend": 95.0},
        "warnings": [],
    }


def _warning_payload():
    return {
        "status": "watch",
        "operational_intelligence_status": "watch",
        "operational_intelligence_score": 62.0,
        "latest_operational_intelligence": {"analysis_id": "lifecycle:intelligence:2026-06-22T00:00:00+00:00"},
        "operational_intelligence_history": [
            {
                "analysis_id": "cycle-warning:intelligence",
                "cycle_id": "cycle-warning",
                "generated_at": "2026-06-22T00:00:00+00:00",
                "operational_intelligence_score": 62.0,
                "warnings": ["queue pressure"],
                "throughput_score": 58.0,
                "anomaly_score": 55.0,
                "compliance_score": 60.0,
                "supervision_score": 54.0,
                "execution_score": 50.0,
                "stability_score": 52.0,
                "operational_intelligence_decision": "defer_supervised_pilot",
                "rfq_trend_score": 60.0,
            }
        ],
        "operational_intelligence_history_summary": {"analysis_count": 1},
        "summary_components": {"rfq_trend": 60.0},
        "warnings": ["queue pressure"],
    }


def _build_service(tmp_path, payload, items, lifecycle, telemetry, review_board, operations, stability, final_readiness, execution):
    module = importlib.import_module("app.services.executive_command_service")
    service = module.ExecutiveCommandService(
        cycle_root=tmp_path / "runtime" / "staging" / "pilot-cycles",
        evidence_pack_root=tmp_path / "runtime" / "staging" / "evidence-packs",
    )
    service.lifecycle = _DummyLifecycleService(items, lifecycle, telemetry)
    service.intelligence = _DummyIntelligenceService(payload)
    service.review_board = _DummyResponseService(review_board)
    service.operations_summary = _DummyResponseService(operations)
    service.stability = _DummyResponseService(stability)
    service.final_readiness = _DummyResponseService(final_readiness)
    service.execution = _DummyResponseService(execution)
    return service


def test_executive_command_service_ready_path(tmp_path):
    service = _build_service(
        tmp_path,
        _ready_payload(),
        [
            {
                "rfq_id": "RFQ-EXEC-001",
                "current_state": "SUBMITTED",
                "submission_method": "portal",
                "submission_status": "submitted",
                "validation_readiness": 96.0,
                "validation_readiness_state": "ready",
                "rfq_lifecycle_duration": 24.0,
            }
        ],
        {
            "generated_at": "2026-06-23T00:00:00+00:00",
            "total_rfqs": 1,
            "queue_trend": {"trend": "stable"},
            "queue_drain_rate": {"overall": 1.3},
            "worker_crash_count": 0,
        },
        {"worker_crash_count": 0, "stalled_lifecycle_tasks": 0, "warnings": [], "system_resilience_score": 96.0},
        {
            "latest_session": {"operator_workload": {"pending_approval_items": [], "assigned_rfqs": ["RFQ-EXEC-001"]}},
            "review_board_cadence": {"runs_last_7_days": 2},
            "outstanding_governance_actions": [],
            "unresolved_operational_exceptions": [],
            "governance_review_history": [{"generated_at": "2026-06-23T00:00:00+00:00"}],
        },
        {
            "status": "ok",
            "operations_summary_status": "ok",
            "summary_components": {"readiness": 96.0, "queue": 95.0},
            "warnings": [],
        },
        {
            "status": "ok",
            "stability_score": 96.0,
            "warnings": [],
            "status": "ok",
        },
        {
            "status": "ok",
            "final_submission_readiness_status": "READY_TO_SUBMIT",
            "final_submission_readiness_score": 96.0,
            "latest_final_readiness": {"final_submission_readiness_status": "READY_TO_SUBMIT"},
            "warnings": [],
        },
        {
            "status": "ok",
            "operational_pilot_execution_status": "ok",
            "operational_endurance_score": 95.0,
            "sustained_stability_score": 95.0,
            "latest_operational_pilot_execution": {"operational_pilot_execution_status": "ok"},
            "warnings": [],
        },
    )

    latest = service.latest_executive_command()
    history = service.executive_command_history(limit=5)

    assert latest["status"] == "ok"
    assert latest["executive_governance_status"] == "ok"
    assert latest["executive_governance_score"] >= 85.0
    assert latest["latest_executive_intelligence"]["institutional_risk_indicators"]["high_risk"] is False
    assert latest["latest_executive_intelligence"]["strategic_readiness_indicators"]["ready_for_controlled_pilot"] is True
    assert latest["latest_executive_intelligence"]["procurement_saturation_indicators"]["review_backlog"] is False
    assert history["count"] >= 1


def test_executive_command_service_warning_path(tmp_path):
    service = _build_service(
        tmp_path,
        _warning_payload(),
        [
            {
                "rfq_id": "RFQ-EXEC-002",
                "current_state": "READY_FOR_RETRY",
                "submission_method": "unknown",
                "submission_status": "unknown",
                "validation_readiness": 44.0,
                "validation_readiness_state": "blocked",
                "rfq_lifecycle_duration": 140.0,
            }
        ],
        {
            "generated_at": "2026-06-22T00:00:00+00:00",
            "total_rfqs": 1,
            "queue_trend": {"trend": "declining"},
            "queue_drain_rate": {"overall": 0.2},
            "worker_crash_count": 2,
        },
        {"worker_crash_count": 2, "stalled_lifecycle_tasks": 3, "warnings": ["broker_backlog"], "system_resilience_score": 52.0},
        {
            "latest_session": {"operator_workload": {"pending_approval_items": ["RFQ-EXEC-002"], "assigned_rfqs": ["RFQ-EXEC-002"]}},
            "review_board_cadence": {"runs_last_7_days": 0},
            "outstanding_governance_actions": ["review escalated exception"],
            "unresolved_operational_exceptions": ["telemetry"],
            "governance_review_history": [{"generated_at": "2026-06-22T00:00:00+00:00"}],
        },
        {
            "status": "watch",
            "operations_summary_status": "watch",
            "summary_components": {"readiness": 48.0, "queue": 42.0},
            "warnings": ["queue pressure"],
        },
        {
            "status": "watch",
            "stability_score": 56.0,
            "warnings": ["drift"],
        },
        {
            "status": "blocked",
            "final_submission_readiness_status": "NOT_READY_TO_SUBMIT",
            "final_submission_readiness_score": 42.0,
            "latest_final_readiness": {"final_submission_readiness_status": "NOT_READY_TO_SUBMIT"},
            "warnings": ["final readiness blocked"],
        },
        {
            "status": "watch",
            "operational_pilot_execution_status": "watch",
            "operational_endurance_score": 44.0,
            "sustained_stability_score": 40.0,
            "latest_operational_pilot_execution": {"operational_pilot_execution_status": "watch"},
            "warnings": ["execution degraded"],
        },
    )

    latest = service.latest_executive_command()

    assert latest["status"] in {"watch", "blocked"}
    assert latest["executive_governance_status"] in {"watch", "blocked"}
    assert latest["latest_executive_intelligence"]["institutional_risk_indicators"]["high_risk"] is True
    assert latest["latest_executive_intelligence"]["strategic_readiness_indicators"]["ready_for_controlled_pilot"] is False
    assert latest["latest_executive_intelligence"]["procurement_saturation_indicators"]["review_backlog"] is True
    assert latest["warnings"]
