from __future__ import annotations

import importlib


class _DummyComplianceService:
    def list_compliance_governance(self, limit: int = 20):
        return {
            "status": "ok",
            "compliance_artifact_governance_status": "ok",
            "compliance_readiness_score": 95.0,
            "tax_clearance_required_count": 1,
            "bbbee_required_count": 1,
            "cidb_required_count": 1,
            "coida_required_count": 1,
            "nhbrc_required_count": 1,
            "company_registration_required_count": 1,
            "bank_letter_required_count": 1,
            "missing_artifact_warning_count": 0,
            "invalid_artifact_indicator_count": 0,
            "expiry_warning_count": 0,
            "compliance_governance_decision_counts": {"approve_compliance_governance": 1},
            "compliance_governance_decision_history": [{"compliance_artifact_governance_id": "RFQ-COMP-001:compliance-governance"}],
            "latest_compliance_governance": {"compliance_artifact_governance_id": "RFQ-COMP-001:compliance-governance"},
            "operator_assignment_readiness_summary": {"ready_count": 1, "not_ready_count": 0, "governance_approval_gate_count": 1},
            "certificate_expiry_governance_summary": {"tax_clearance": {"required_count": 1, "present_count": 1, "valid_count": 1}},
            "warnings": [],
        }

    def latest_compliance_governance(self):
        return {
            "status": "ok",
            "compliance_artifact_governance_status": "ok",
            "compliance_readiness_score": 95.0,
            "latest_compliance_governance": {"compliance_artifact_governance_id": "RFQ-COMP-001:compliance-governance"},
            "compliance_governance_decision_history": [{"compliance_artifact_governance_id": "RFQ-COMP-001:compliance-governance"}],
            "compliance_governance_decision_counts": {"approve_compliance_governance": 1},
            "operator_assignment_readiness_summary": {"ready_count": 1, "not_ready_count": 0, "governance_approval_gate_count": 1},
            "certificate_expiry_governance_summary": {"tax_clearance": {"required_count": 1, "present_count": 1, "valid_count": 1}},
            "warnings": [],
        }

    def compliance_governance_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "compliance_governance_decision_history": [{"compliance_artifact_governance_id": "RFQ-COMP-001:compliance-governance"}],
            "compliance_governance_decision_counts": {"approve_compliance_governance": 1},
            "operator_assignment_readiness_summary": {"ready_count": 1, "not_ready_count": 0, "governance_approval_gate_count": 1},
            "certificate_expiry_governance_summary": {"tax_clearance": {"required_count": 1, "present_count": 1, "valid_count": 1}},
            "warnings": [],
        }


def test_compliance_governance_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "compliance_governance_service", lambda: _DummyComplianceService())

    assert module.compliance_governance(limit=5)["compliance_artifact_governance_status"] == "ok"
    assert module.compliance_governance_latest()["latest_compliance_governance"]["compliance_artifact_governance_id"] == "RFQ-COMP-001:compliance-governance"
    assert module.compliance_governance_history(limit=5)["count"] == 1
