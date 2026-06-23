from __future__ import annotations

import importlib


class _DummySummaryService:
    def list_operations_summary(self, limit: int = 20):
        return {
            "status": "ok",
            "operations_summary_status": "ok",
            "consolidated_governance_score": 92.0,
            "consolidated_governance_grade": "ok",
            "readiness_status": "ok",
            "stability_status": "ok",
            "remediation_status": "ok",
            "progression_status": "ok",
            "no_go_status": "PASS",
            "cadence_status": "on_track",
            "exception_status": "ok",
            "governance_review_status": "ok",
            "consolidated_watch_indicators": {"readiness_watch": False},
            "unresolved_blocker_summary": {"open_remediation_count": 0, "blocking_remediation_count": 0, "open_exception_count": 0},
            "governance_recommendation_summary": {"recommendation": "pilot_continuation_review", "rationale": ["Continue."]},
            "summary_components": {"readiness": 92.0},
            "institutional_operational_summary_history": [{"summary_id": "summary-1"}],
            "warning_indicators": {"missing_summary_history": False},
            "warnings": [],
        }

    def latest_operations_summary(self):
        return {
            "status": "ok",
            "operations_summary_status": "ok",
            "consolidated_governance_score": 92.0,
            "consolidated_governance_grade": "ok",
            "readiness_status": "ok",
            "stability_status": "ok",
            "remediation_status": "ok",
            "progression_status": "ok",
            "no_go_status": "PASS",
            "cadence_status": "on_track",
            "exception_status": "ok",
            "governance_review_status": "ok",
            "consolidated_watch_indicators": {"readiness_watch": False},
            "unresolved_blocker_summary": {"open_remediation_count": 0, "blocking_remediation_count": 0, "open_exception_count": 0},
            "governance_recommendation_summary": {"recommendation": "pilot_continuation_review", "rationale": ["Continue."]},
            "summary_components": {"readiness": 92.0},
            "latest_summary": {"summary_id": "summary-1"},
            "warning_indicators": {"missing_summary_history": False},
            "warnings": [],
        }

    def operations_summary_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "institutional_operational_summary_history": [{"summary_id": "summary-1"}],
            "consolidated_governance_score": 92.0,
            "consolidated_governance_grade": "ok",
            "consolidated_watch_indicators": {"readiness_watch": False},
            "unresolved_blocker_summary": {"open_remediation_count": 0, "blocking_remediation_count": 0, "open_exception_count": 0},
            "governance_recommendation_summary": {"recommendation": "pilot_continuation_review", "rationale": ["Continue."]},
            "summary_components": {"readiness": 92.0},
            "warning_indicators": {"missing_summary_history": False},
            "warnings": [],
        }


def test_operations_summary_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "operations_summary_service", lambda: _DummySummaryService())

    assert module.operations_summary(limit=5)["status"] == "ok"
    assert module.operations_summary_latest()["operations_summary_status"] == "ok"
    assert module.operations_summary_history(limit=5)["count"] == 1
