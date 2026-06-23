from __future__ import annotations

import importlib


class _DummyPhysicalService:
    def list_physical_submissions(self, limit: int = 20):
        return {
            "status": "ok",
            "physical_rfq_governance_status": "ok",
            "physical_submission_readiness_score": 96.0,
            "physical_submission_classification": "courier_hand_delivery",
            "physical_submission_required_count": 1,
            "courier_manual_delivery_count": 1,
            "chain_of_custody_count": 1,
            "pod_evidence_count": 1,
            "submission_pack_ready_count": 1,
            "manual_handoff_count": 1,
            "governance_approval_gate_count": 1,
            "operator_assignment_ready_count": 1,
            "delivery_deadline_warning_count": 0,
            "missing_proof_warning_count": 0,
            "physical_submission_decision_counts": {"approve_physical_submission": 1},
            "physical_submission_warning_indicators": {"delivery_deadline_warning": False},
            "physical_submission_decision_history": [{"physical_submission_id": "RFQ-PHYSICAL-001:physical-submission"}],
            "latest_physical_submission": {"physical_submission_id": "RFQ-PHYSICAL-001:physical-submission"},
            "warnings": [],
        }

    def latest_physical_submission(self):
        return {
            "status": "ok",
            "physical_rfq_governance_status": "ok",
            "physical_submission_readiness_score": 96.0,
            "physical_submission_classification": "courier_hand_delivery",
            "latest_physical_submission": {"physical_submission_id": "RFQ-PHYSICAL-001:physical-submission"},
            "physical_submission_decision_history": [{"physical_submission_id": "RFQ-PHYSICAL-001:physical-submission"}],
            "physical_submission_decision_counts": {"approve_physical_submission": 1},
            "physical_submission_warning_indicators": {"delivery_deadline_warning": False},
            "warnings": [],
        }

    def physical_submission_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "physical_submission_decision_history": [{"physical_submission_id": "RFQ-PHYSICAL-001:physical-submission"}],
            "physical_submission_decision_counts": {"approve_physical_submission": 1},
            "physical_submission_warning_indicators": {"delivery_deadline_warning": False},
            "warnings": [],
        }


def test_physical_submission_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "physical_submission_service", lambda: _DummyPhysicalService())

    assert module.physical_submission(limit=5)["physical_rfq_governance_status"] == "ok"
    assert module.physical_submission_latest()["physical_submission_classification"] == "courier_hand_delivery"
    assert module.physical_submission_history(limit=5)["count"] == 1
