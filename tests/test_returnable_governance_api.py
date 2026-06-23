from __future__ import annotations

import importlib


class _DummyReturnableService:
    def list_returnable_governance(self, limit: int = 20):
        return {
            "status": "ok",
            "returnable_governance_status": "ok",
            "bid_response_completeness_score": 95.0,
            "annexure_classification_counts": {"annexure_detected": 1, "annexure_missing": 0},
            "mandatory_returnable_count": 1,
            "pricing_schedule_complete_count": 1,
            "declaration_complete_count": 1,
            "technical_schedule_complete_count": 1,
            "compulsory_form_ready_count": 1,
            "mandatory_attachment_complete_count": 1,
            "incomplete_returnable_warning_count": 0,
            "missing_annexure_indicator_count": 0,
            "unsigned_returnable_warning_count": 0,
            "returnable_governance_decision_counts": {"approve_returnable_governance": 1},
            "returnable_governance_history": [{"returnable_governance_id": "RFQ-RET-001:returnable-governance"}],
            "latest_returnable_governance": {"returnable_governance_id": "RFQ-RET-001:returnable-governance"},
            "operator_assignment_readiness_summary": {"ready_count": 1, "not_ready_count": 0, "governance_approval_gate_count": 1},
            "warnings": [],
        }

    def latest_returnable_governance(self):
        return {
            "status": "ok",
            "returnable_governance_status": "ok",
            "bid_response_completeness_score": 95.0,
            "latest_returnable_governance": {"returnable_governance_id": "RFQ-RET-001:returnable-governance"},
            "returnable_governance_history": [{"returnable_governance_id": "RFQ-RET-001:returnable-governance"}],
            "returnable_governance_decision_counts": {"approve_returnable_governance": 1},
            "operator_assignment_readiness_summary": {"ready_count": 1, "not_ready_count": 0, "governance_approval_gate_count": 1},
            "warnings": [],
        }

    def returnable_governance_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "returnable_governance_history": [{"returnable_governance_id": "RFQ-RET-001:returnable-governance"}],
            "returnable_governance_decision_counts": {"approve_returnable_governance": 1},
            "operator_assignment_readiness_summary": {"ready_count": 1, "not_ready_count": 0, "governance_approval_gate_count": 1},
            "warnings": [],
        }


def test_returnable_governance_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "returnable_governance_service", lambda: _DummyReturnableService())

    assert module.returnable_governance(limit=5)["returnable_governance_status"] == "ok"
    assert module.returnable_governance_latest()["latest_returnable_governance"]["returnable_governance_id"] == "RFQ-RET-001:returnable-governance"
    assert module.returnable_governance_history(limit=5)["count"] == 1
