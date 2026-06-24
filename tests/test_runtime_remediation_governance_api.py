from __future__ import annotations

import importlib


class _DummyRuntimeRemediationService:
    def list_runtime_remediation(self, limit: int = 20):
        return {
            "status": "watch",
            "generated_at": "2026-06-24T01:00:00+00:00",
            "latest_cycle": {"validation_id": "runtime-endurance-warn", "runtime_endurance_status": "WARN", "runtime_endurance_score": 76.0},
            "runtime_remediation_status": "watch",
            "runtime_remediation_summary": {
                "total_remediation_count": 1,
                "open_remediation_count": 1,
                "resolved_remediation_count": 0,
                "blocking_remediation_count": 0,
                "remediation_readiness_score": 76.0,
                "remediation_readiness_status": "WARN",
            },
            "remediation_classifications": [{"remediation_id": "runtime-endurance-warn:observability_failure"}],
            "endurance_degradation_findings": [{"remediation_id": "runtime-endurance-warn:observability_failure"}],
            "open_remediation_tracking": [{"remediation_id": "runtime-endurance-warn:observability_failure"}],
            "resolved_remediation_history": [],
            "unresolved_remediation_blockers": [],
            "remediation_escalation_indicators": {"observability_failure_found": True},
            "governance_recovery_tracking": {"governance_recovery_ready": False},
            "remediation_governance_history": {"analysis_count": 1, "latest_analysis_id": "runtime-endurance-warn"},
            "remediation_rationale_summary": ["Observability endpoints remain reachable: FAIL."],
            "warning_indicators": {"observability_failure_warning": True},
            "warnings": ["observability_failure_warning"],
            "latest_runtime_endurance": {"validation_id": "runtime-endurance-warn"},
        }

    def latest_runtime_remediation(self):
        return self.list_runtime_remediation()

    def runtime_remediation_history(self, limit: int = 20):
        return {
            "status": "watch",
            "count": 1,
            "runtime_remediation_history": [{"analysis_id": "runtime-endurance-warn", "runtime_remediation_status": "watch"}],
            "runtime_remediation_summary": {"status": "WARN"},
            "remediation_governance_history": {"analysis_count": 1, "latest_analysis_id": "runtime-endurance-warn"},
            "warnings": ["observability_failure_warning"],
        }


def test_runtime_remediation_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "runtime_remediation_governance_service", lambda: _DummyRuntimeRemediationService())

    assert module.runtime_remediation(limit=5)["status"] == "watch"
    assert module.runtime_remediation_latest()["runtime_remediation_status"] == "watch"
    assert module.runtime_remediation_history(limit=5)["count"] == 1
