from __future__ import annotations

import importlib


class _DummyProgressionService:
    def list_progression(self, limit: int = 20):
        return {
            "status": "watch",
            "progression_status": "watch",
            "progression_score": 88.0,
            "progression_grade": "watch",
            "progression_decision": "pilot_continuation_review",
            "pilot_progression_score": 88.0,
            "pilot_progression_grade": "watch",
            "pilot_progression_summary": {
                "continuation_review": True,
                "watch_review": False,
                "closure_review": False,
                "expansion_review": False,
                "unresolved_anomaly_impact_review": False,
            },
            "expansion_eligibility_indicators": {
                "continuation_eligible": True,
                "watch_eligible": False,
                "closure_eligible": True,
                "expansion_eligible": False,
            },
            "unresolved_blocker_summary": {
                "open_remediation_count": 0,
                "overdue_remediation_count": 0,
                "open_exception_count": 0,
                "blocking_remediation_count": 0,
            },
            "progression_decision_history": [{"progression_id": "review-1:progression"}],
            "governance_rationale_summary": {"status": "PASS", "rationale": ["Readiness is sufficient."]},
            "governance_progression_decisions": ["pilot_continuation_review"],
            "warning_indicators": {"missing_progression_history": False},
            "warnings": [],
            "latest_review_board_status": "ok",
        }

    def latest_progression(self):
        return {
            "status": "watch",
            "progression_status": "watch",
            "progression_score": 88.0,
            "progression_grade": "watch",
            "progression_decision": "pilot_continuation_review",
            "pilot_progression_score": 88.0,
            "pilot_progression_grade": "watch",
            "pilot_progression_summary": {"continuation_review": True},
            "expansion_eligibility_indicators": {"continuation_eligible": True, "watch_eligible": False, "closure_eligible": True, "expansion_eligible": False},
            "unresolved_blocker_summary": {"open_remediation_count": 0, "overdue_remediation_count": 0, "open_exception_count": 0, "blocking_remediation_count": 0},
            "progression_decision_history": [{"progression_id": "review-1:progression"}],
            "governance_rationale_summary": {"status": "PASS", "rationale": ["Readiness is sufficient."]},
            "governance_progression_decisions": ["pilot_continuation_review"],
            "warning_indicators": {"missing_progression_history": False},
            "warnings": [],
        }

    def progression_history(self, limit: int = 20):
        return {
            "status": "watch",
            "count": 1,
            "progression_decision_history": [{"progression_id": "review-1:progression"}],
            "expansion_eligibility_indicators": {"continuation_eligible": True, "closure_eligible": True, "expansion_eligible": False},
            "unresolved_blocker_summary": {"open_remediation_count": 0, "blocking_remediation_count": 0},
            "governance_rationale_summary": {"status": "PASS"},
            "governance_progression_decisions": ["pilot_continuation_review"],
            "pilot_progression_score": 88.0,
            "pilot_progression_grade": "watch",
            "warning_indicators": {"missing_progression_history": False},
            "warnings": [],
        }


def test_progression_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "progression_service", lambda: _DummyProgressionService())

    assert module.progression(limit=5)["progression_decision"] == "pilot_continuation_review"
    assert module.progression_latest()["progression_status"] == "watch"
    assert module.progression_history(limit=5)["count"] == 1
