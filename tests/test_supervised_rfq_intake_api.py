from __future__ import annotations

import importlib


class _DummyIntakeService:
    def list_intake(self, limit: int = 20):
        return {
            "status": "ok",
            "intake_status": "ok",
            "intake_eligibility_score": 95.0,
            "intake_eligibility_grade": "ready",
            "restricted_category_warnings": [],
            "supervision_capacity_indicators": {"coverage_ok": True, "capacity_warning_count": 0},
            "governance_intake_decisions": [{"intake_id": "cycle-1:REHEARSAL-RETRY-001:intake"}],
            "intake_decision_history": [{"intake_id": "cycle-1:REHEARSAL-RETRY-001:intake"}],
            "pilot_scope_enforcement": {"pilot_scope_valid_count": 1, "pilot_scope_invalid_count": 0, "restricted_category_count": 0},
            "operator_assignment_readiness": {"ready_count": 1, "not_ready_count": 0, "governance_approval_gate_count": 1, "governance_approval_block_count": 0},
            "latest_intake": {"intake_id": "cycle-1:REHEARSAL-RETRY-001:intake"},
            "warning_indicators": {"restricted_category_warning": False},
            "warnings": [],
        }

    def latest_intake(self):
        return {
            "status": "ok",
            "intake_status": "ok",
            "intake_eligibility_score": 95.0,
            "intake_eligibility_grade": "ready",
            "latest_intake": {"intake_id": "cycle-1:REHEARSAL-RETRY-001:intake"},
            "governance_intake_decisions": [{"intake_id": "cycle-1:REHEARSAL-RETRY-001:intake"}],
            "intake_decision_history": [{"intake_id": "cycle-1:REHEARSAL-RETRY-001:intake"}],
            "restricted_category_warnings": [],
            "supervision_capacity_indicators": {"coverage_ok": True, "capacity_warning_count": 0},
            "pilot_scope_enforcement": {"pilot_scope_valid_count": 1, "pilot_scope_invalid_count": 0, "restricted_category_count": 0},
            "operator_assignment_readiness": {"ready_count": 1, "not_ready_count": 0, "governance_approval_gate_count": 1, "governance_approval_block_count": 0},
            "warning_indicators": {"restricted_category_warning": False},
            "warnings": [],
        }

    def intake_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "intake_decision_history": [{"intake_id": "cycle-1:REHEARSAL-RETRY-001:intake"}],
            "governance_intake_decisions": [{"intake_id": "cycle-1:REHEARSAL-RETRY-001:intake"}],
            "restricted_category_warnings": [],
            "supervision_capacity_indicators": {"coverage_ok": True, "capacity_warning_count": 0},
            "pilot_scope_enforcement": {"pilot_scope_valid_count": 1, "pilot_scope_invalid_count": 0, "restricted_category_count": 0},
            "operator_assignment_readiness": {"ready_count": 1, "not_ready_count": 0, "governance_approval_gate_count": 1, "governance_approval_block_count": 0},
            "warning_indicators": {"restricted_category_warning": False},
            "warnings": [],
        }


def test_supervised_rfq_intake_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "intake_service", lambda: _DummyIntakeService())

    assert module.intake(limit=5)["intake_status"] == "ok"
    assert module.intake_latest()["intake_eligibility_grade"] == "ready"
    assert module.intake_history(limit=5)["count"] == 1
