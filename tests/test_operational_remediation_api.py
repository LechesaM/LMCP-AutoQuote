from __future__ import annotations

import importlib


class _DummyRemediationService:
    def list_remediation(self, limit: int = 20):
        return {
            "status": "watch",
            "remediation_summary": {"total_remediation_count": 1, "open_remediation_count": 1, "resolved_remediation_count": 0, "overdue_remediation_count": 1, "blocking_remediation_count": 1, "accepted_risk_remediation_count": 0},
            "remediation_actions": [{"remediation_id": "cycle-1:remediation", "category": "governance_compliance_failure", "owner": "governance", "completion_status": "overdue", "deadline_at": "2026-06-24T11:30:52+00:00", "overdue": True}],
            "open_remediation_tracking": [{"remediation_id": "cycle-1:remediation"}],
            "resolved_remediation_history": [],
            "unresolved_blocker_tracking": [{"remediation_id": "cycle-1:remediation"}],
            "operational_risk_closure_summary": {"status": "WARN", "open_count": 1, "closed_count": 0, "overdue_count": 1, "accepted_risk_count": 0},
            "remediation_governance_history": {"status": "WARN", "remediation_count": 1, "category_counts": {"governance_compliance_failure": 1}, "latest_remediation_id": "cycle-1:remediation", "latest_deadline_at": "2026-06-24T11:30:52+00:00", "latest_owner": "governance"},
            "operational_risk_indicators": {"overdue_remediation_warning": True, "unresolved_blocker_warning": True, "accepted_risk_warning": False, "history_warning": True},
            "warning_indicators": {"overdue_remediation_warning": True, "unresolved_blocker_warning": True, "accepted_risk_warning": False, "history_warning": True},
            "warnings": ["overdue_remediation_warning", "unresolved_blocker_warning", "history_warning"],
            "latest_cycle": {"cycle_id": "cycle-1"},
            "latest_governance_export": {"export_id": "export-1"},
            "remediation_status": "watch",
        }

    def latest_remediation(self):
        return {
            "status": "watch",
            "latest_cycle": {"cycle_id": "cycle-1"},
            "latest_governance_export": {"export_id": "export-1"},
            "remediation_status": "watch",
            "remediation_summary": {"total_remediation_count": 1, "open_remediation_count": 1, "resolved_remediation_count": 0, "overdue_remediation_count": 1, "blocking_remediation_count": 1, "accepted_risk_remediation_count": 0},
            "remediation_actions": [{"remediation_id": "cycle-1:remediation", "category": "governance_compliance_failure", "owner": "governance", "completion_status": "overdue", "deadline_at": "2026-06-24T11:30:52+00:00", "overdue": True}],
            "open_remediation_tracking": [{"remediation_id": "cycle-1:remediation"}],
            "resolved_remediation_history": [],
            "unresolved_blocker_tracking": [{"remediation_id": "cycle-1:remediation"}],
            "operational_risk_closure_summary": {"status": "WARN", "open_count": 1, "closed_count": 0, "overdue_count": 1, "accepted_risk_count": 0},
            "remediation_governance_history": {"status": "WARN"},
            "operational_risk_indicators": {"overdue_remediation_warning": True, "unresolved_blocker_warning": True, "accepted_risk_warning": False, "history_warning": True},
            "warning_indicators": {"overdue_remediation_warning": True, "unresolved_blocker_warning": True, "accepted_risk_warning": False, "history_warning": True},
            "warnings": ["overdue_remediation_warning", "unresolved_blocker_warning", "history_warning"],
        }

    def remediation_history(self, limit: int = 20):
        return {
            "status": "watch",
            "count": 1,
            "remediation_actions": [{"remediation_id": "cycle-1:remediation", "category": "governance_compliance_failure"}],
            "open_remediation_tracking": [{"remediation_id": "cycle-1:remediation"}],
            "resolved_remediation_history": [],
            "unresolved_blocker_tracking": [{"remediation_id": "cycle-1:remediation"}],
            "remediation_summary": {"status": "WARN"},
            "operational_risk_closure_summary": {"status": "WARN"},
            "remediation_governance_history": {"status": "WARN"},
            "operational_risk_indicators": {"overdue_remediation_warning": True},
            "warning_indicators": {"overdue_remediation_warning": True},
            "warnings": ["overdue_remediation_warning"],
        }


def test_remediation_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "remediation_service", lambda: _DummyRemediationService())

    assert module.remediation(limit=5)["status"] == "watch"
    assert module.remediation_latest()["remediation_status"] == "watch"
    assert module.remediation_history(limit=5)["count"] == 1
