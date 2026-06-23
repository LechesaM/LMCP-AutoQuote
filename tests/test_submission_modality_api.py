from __future__ import annotations

import importlib


class _DummyModalityService:
    def list_submission_modalities(self, limit: int = 20):
        return {
            "status": "ok",
            "submission_modality_status": "ok",
            "modality_governance_score": 95.0,
            "selected_modality": "email",
            "fallback_modality": "email",
            "supported_modality_counts": {"email": 1, "portal": 1, "physical": 1},
            "mixed_modality_rfq_count": 1,
            "unsupported_modality_warning_count": 0,
            "portal_email_conflict_count": 0,
            "physical_digital_conflict_count": 0,
            "governance_approval_gate_count": 1,
            "operator_assignment_ready_count": 1,
            "submission_channel_governance_summaries": [{"email_supported": True}],
            "modality_decision_counts": {"approve_modality": 1},
            "modality_decision_history": [{"submission_modality_id": "RFQ-MODALITY-001:modality"}],
            "latest_submission_modality": {"submission_modality_id": "RFQ-MODALITY-001:modality"},
            "warnings": [],
        }

    def latest_submission_modality(self):
        return {
            "status": "ok",
            "submission_modality_status": "ok",
            "modality_governance_score": 95.0,
            "selected_modality": "email",
            "fallback_modality": "email",
            "submission_channel_governance_summaries": [{"email_supported": True}],
            "modality_decision_history": [{"submission_modality_id": "RFQ-MODALITY-001:modality"}],
            "modality_decision_counts": {"approve_modality": 1},
            "latest_submission_modality": {"submission_modality_id": "RFQ-MODALITY-001:modality"},
            "warnings": [],
        }

    def submission_modality_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "modality_decision_history": [{"submission_modality_id": "RFQ-MODALITY-001:modality"}],
            "modality_decision_counts": {"approve_modality": 1},
            "submission_channel_governance_summaries": [{"email_supported": True}],
            "warnings": [],
        }


def test_submission_modality_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "submission_modality_service", lambda: _DummyModalityService())

    assert module.submission_modality(limit=5)["submission_modality_status"] == "ok"
    assert module.submission_modality_latest()["selected_modality"] == "email"
    assert module.submission_modality_history(limit=5)["count"] == 1
