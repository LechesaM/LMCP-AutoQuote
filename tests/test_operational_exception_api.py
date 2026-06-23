from __future__ import annotations

import importlib


class _DummyExceptionService:
    def list_exceptions(self, limit: int = 20):
        return {
            "status": "watch",
            "exception_summary": {
                "total_exception_count": 1,
                "open_exception_count": 0,
                "resolved_exception_count": 1,
                "transient_failure_count": 1,
                "systemic_failure_count": 0,
                "retry_exhaustion_count": 0,
                "telemetry_degradation_count": 0,
                "queue_instability_count": 0,
                "operator_intervention_anomaly_count": 0,
                "governance_compliance_failure_count": 0,
            },
            "remediation_status_summary": {"status": "PASS", "unresolved_count": 0, "resolved_count": 1, "open_categories": [], "resolved_categories": ["transient_failure"], "category_counts": {"transient_failure": 1}},
            "unresolved_exception_tracking": [],
            "resolved_exception_history": [{"exception_id": "cycle-1:1:transient_failure"}],
            "operational_risk_indicators": {"repeated_exception_types": ["transient_failure"], "governance_compliance_risk": False, "telemetry_degradation_risk": False, "queue_instability_risk": False, "retry_exhaustion_risk": False, "operator_intervention_risk": False, "systemic_failure_risk": False, "open_exception_count": 0, "resolved_exception_count": 1, "latest_readiness_score": 100.0, "latest_readiness_grade": "ready", "latest_exception_age_hours": 0.0},
            "recurring_anomaly_summary": {"status": "WARN", "category_counts": {"transient_failure": 1}, "latest_exception_type": "transient_failure", "latest_exception_at": "2026-06-23T11:30:52+00:00", "most_common_exception_type": "transient_failure", "recurring_anomaly_counts": {"transient_failure": 1}, "history_window_days": 30},
            "classification_history": [{"exception_id": "cycle-1:1:transient_failure"}],
            "warning_indicators": {"repeated_exception_warning": True},
            "warnings": ["repeated_exception_warning"],
            "latest_cycle": {"cycle_id": "cycle-1"},
            "latest_governance_export": {"export_id": "export-1"},
            "exception_status": "watch",
        }

    def latest_exceptions(self):
        return {
            "status": "watch",
            "latest_cycle": {"cycle_id": "cycle-1"},
            "latest_governance_export": {"export_id": "export-1"},
            "exception_status": "watch",
            "exception_summary": {"total_exception_count": 1},
            "remediation_status_summary": {"status": "PASS"},
            "operational_risk_indicators": {"repeated_exception_types": ["transient_failure"]},
            "recurring_anomaly_summary": {"status": "WARN"},
            "unresolved_exception_tracking": [],
            "resolved_exception_history": [{"exception_id": "cycle-1:1:transient_failure"}],
            "warning_indicators": {"repeated_exception_warning": True},
            "warnings": ["repeated_exception_warning"],
        }

    def exceptions_history(self, limit: int = 20):
        return {
            "status": "watch",
            "count": 1,
            "classification_history": [{"exception_id": "cycle-1:1:transient_failure"}],
            "unresolved_exception_tracking": [],
            "resolved_exception_history": [{"exception_id": "cycle-1:1:transient_failure"}],
            "exception_summary": {"total_exception_count": 1},
            "remediation_status_summary": {"status": "PASS"},
            "operational_risk_indicators": {"repeated_exception_types": ["transient_failure"]},
            "recurring_anomaly_summary": {"status": "WARN"},
            "warning_indicators": {"repeated_exception_warning": True},
            "warnings": ["repeated_exception_warning"],
        }


def test_exception_routes_expose_read_only_classification(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "exception_service", lambda: _DummyExceptionService())

    assert module.exceptions(limit=5)["status"] == "watch"
    assert module.exceptions_latest()["exception_status"] == "watch"
    assert module.exceptions_history(limit=5)["count"] == 1
