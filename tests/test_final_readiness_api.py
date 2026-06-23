from __future__ import annotations

import importlib


class _DummyFinalReadinessService:
    def list_final_readiness(self, limit: int = 20):
        return {
            "status": "ok",
            "final_submission_readiness_status": "READY_TO_SUBMIT",
            "final_submission_readiness_score": 96.5,
            "final_submission_ready_count": 1,
            "final_submission_not_ready_count": 0,
            "unresolved_blocker_count": 0,
            "governance_override_count": 0,
            "final_submission_readiness_decision_counts": {"authorise_final_submission": 1},
            "final_escalation_authority_counts": {"operator_session": 1},
            "final_readiness_history": [{"final_readiness_id": "RFQ-FR-001:final-readiness"}],
            "latest_final_readiness": {"final_readiness_id": "RFQ-FR-001:final-readiness"},
            "final_readiness_rationale_history": [{"final_readiness_id": "RFQ-FR-001:final-readiness"}],
            "operator_assignment_readiness_summary": {"ready_count": 1, "not_ready_count": 0, "governance_approval_gate_count": 1},
            "warnings": [],
        }

    def latest_final_readiness(self):
        return {
            "status": "ok",
            "final_submission_readiness_status": "READY_TO_SUBMIT",
            "final_submission_readiness_score": 96.5,
            "latest_final_readiness": {"final_readiness_id": "RFQ-FR-001:final-readiness"},
            "final_readiness_history": [{"final_readiness_id": "RFQ-FR-001:final-readiness"}],
            "final_readiness_rationale_history": [{"final_readiness_id": "RFQ-FR-001:final-readiness"}],
            "final_submission_readiness_decision_counts": {"authorise_final_submission": 1},
            "final_escalation_authority_counts": {"operator_session": 1},
            "operator_assignment_readiness_summary": {"ready_count": 1, "not_ready_count": 0, "governance_approval_gate_count": 1},
            "warnings": [],
        }

    def final_readiness_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "final_readiness_history": [{"final_readiness_id": "RFQ-FR-001:final-readiness"}],
            "final_readiness_rationale_history": [{"final_readiness_id": "RFQ-FR-001:final-readiness"}],
            "final_submission_readiness_decision_counts": {"authorise_final_submission": 1},
            "final_escalation_authority_counts": {"operator_session": 1},
            "operator_assignment_readiness_summary": {"ready_count": 1, "not_ready_count": 0, "governance_approval_gate_count": 1},
            "warnings": [],
        }


def test_final_readiness_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "final_readiness_service", lambda: _DummyFinalReadinessService())

    assert module.final_readiness(limit=5)["final_submission_readiness_status"] == "READY_TO_SUBMIT"
    assert module.final_readiness_latest()["latest_final_readiness"]["final_readiness_id"] == "RFQ-FR-001:final-readiness"
    assert module.final_readiness_history(limit=5)["count"] == 1
