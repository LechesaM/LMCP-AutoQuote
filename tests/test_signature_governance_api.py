from __future__ import annotations

import importlib


class _DummySignatureService:
    def list_signature_governance(self, limit: int = 20):
        return {
            "status": "ok",
            "signature_governance_status": "ok",
            "signature_governance_score": 95.0,
            "wet_signature_required_count": 1,
            "handwritten_declaration_required_count": 1,
            "witness_required_count": 1,
            "commissioner_required_count": 1,
            "affidavit_required_count": 1,
            "manual_attestation_required_count": 1,
            "signature_governance_decision_counts": {"approve_signature_governance": 1},
            "signature_governance_decision_history": [{"signature_governance_id": "RFQ-SIGN-001:signature-governance"}],
            "latest_signature_governance": {"signature_governance_id": "RFQ-SIGN-001:signature-governance"},
            "operator_assignment_readiness_summary": {"ready_count": 1, "not_ready_count": 0, "governance_approval_gate_count": 1},
            "unsigned_document_warning_count": 0,
            "human_completion_required_warning_count": 0,
            "warnings": [],
        }

    def latest_signature_governance(self):
        return {
            "status": "ok",
            "signature_governance_status": "ok",
            "signature_governance_score": 95.0,
            "latest_signature_governance": {"signature_governance_id": "RFQ-SIGN-001:signature-governance"},
            "signature_governance_decision_history": [{"signature_governance_id": "RFQ-SIGN-001:signature-governance"}],
            "signature_governance_decision_counts": {"approve_signature_governance": 1},
            "operator_assignment_readiness_summary": {"ready_count": 1, "not_ready_count": 0, "governance_approval_gate_count": 1},
            "warnings": [],
        }

    def signature_governance_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "signature_governance_decision_history": [{"signature_governance_id": "RFQ-SIGN-001:signature-governance"}],
            "signature_governance_decision_counts": {"approve_signature_governance": 1},
            "operator_assignment_readiness_summary": {"ready_count": 1, "not_ready_count": 0, "governance_approval_gate_count": 1},
            "warnings": [],
        }


def test_signature_governance_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "signature_governance_service", lambda: _DummySignatureService())

    assert module.signature_governance(limit=5)["signature_governance_status"] == "ok"
    assert module.signature_governance_latest()["latest_signature_governance"]["signature_governance_id"] == "RFQ-SIGN-001:signature-governance"
    assert module.signature_governance_history(limit=5)["count"] == 1
