from __future__ import annotations

import importlib


class _DummyDeadlineService:
    def list_deadline_governance(self, limit: int = 20):
        return {
            "status": "ok",
            "deadline_governance_status": "ok",
            "timing_readiness_score": 95.0,
            "submission_cutoff_warning_count": 0,
            "upload_window_open_count": 1,
            "courier_timing_warning_count": 0,
            "portal_timeout_warning_count": 0,
            "escalation_timing_warning_count": 0,
            "late_submission_prevention_count": 0,
            "deadline_governance_decision_counts": {"approve_deadline_governance": 1},
            "deadline_governance_history": [{"deadline_governance_id": "RFQ-DL-001:deadline-governance"}],
            "latest_deadline_governance": {"deadline_governance_id": "RFQ-DL-001:deadline-governance"},
            "operator_assignment_readiness_summary": {"ready_count": 1, "not_ready_count": 0, "governance_approval_gate_count": 1},
            "warnings": [],
        }

    def latest_deadline_governance(self):
        return {
            "status": "ok",
            "deadline_governance_status": "ok",
            "timing_readiness_score": 95.0,
            "latest_deadline_governance": {"deadline_governance_id": "RFQ-DL-001:deadline-governance"},
            "deadline_governance_history": [{"deadline_governance_id": "RFQ-DL-001:deadline-governance"}],
            "deadline_governance_decision_counts": {"approve_deadline_governance": 1},
            "operator_assignment_readiness_summary": {"ready_count": 1, "not_ready_count": 0, "governance_approval_gate_count": 1},
            "warnings": [],
        }

    def deadline_governance_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "deadline_governance_history": [{"deadline_governance_id": "RFQ-DL-001:deadline-governance"}],
            "deadline_governance_decision_counts": {"approve_deadline_governance": 1},
            "operator_assignment_readiness_summary": {"ready_count": 1, "not_ready_count": 0, "governance_approval_gate_count": 1},
            "warnings": [],
        }


def test_deadline_governance_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "deadline_governance_service", lambda: _DummyDeadlineService())

    assert module.deadline_governance(limit=5)["deadline_governance_status"] == "ok"
    assert module.deadline_governance_latest()["latest_deadline_governance"]["deadline_governance_id"] == "RFQ-DL-001:deadline-governance"
    assert module.deadline_governance_history(limit=5)["count"] == 1
