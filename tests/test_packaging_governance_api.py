from __future__ import annotations

import importlib


class _DummyPackagingService:
    def list_packaging_governance(self, limit: int = 20):
        return {
            "status": "ok",
            "packaging_governance_status": "ok",
            "packaging_readiness_score": 95.0,
            "submission_bundle_complete_count": 1,
            "attachment_bundle_valid_count": 1,
            "zip_package_integrity_count": 1,
            "print_pack_ready_count": 1,
            "folder_structure_valid_count": 1,
            "naming_convention_count": 1,
            "upload_package_ready_count": 1,
            "incomplete_package_warning_count": 0,
            "malformed_bundle_indicator_count": 0,
            "missing_attachment_warning_count": 0,
            "packaging_governance_decision_counts": {"approve_packaging_governance": 1},
            "packaging_governance_history": [{"packaging_governance_id": "RFQ-PKG-001:packaging-governance"}],
            "latest_packaging_governance": {"packaging_governance_id": "RFQ-PKG-001:packaging-governance"},
            "operator_assignment_readiness_summary": {"ready_count": 1, "not_ready_count": 0, "governance_approval_gate_count": 1},
            "warnings": [],
        }

    def latest_packaging_governance(self):
        return {
            "status": "ok",
            "packaging_governance_status": "ok",
            "packaging_readiness_score": 95.0,
            "latest_packaging_governance": {"packaging_governance_id": "RFQ-PKG-001:packaging-governance"},
            "packaging_governance_history": [{"packaging_governance_id": "RFQ-PKG-001:packaging-governance"}],
            "packaging_governance_decision_counts": {"approve_packaging_governance": 1},
            "operator_assignment_readiness_summary": {"ready_count": 1, "not_ready_count": 0, "governance_approval_gate_count": 1},
            "warnings": [],
        }

    def packaging_governance_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "packaging_governance_history": [{"packaging_governance_id": "RFQ-PKG-001:packaging-governance"}],
            "packaging_governance_decision_counts": {"approve_packaging_governance": 1},
            "operator_assignment_readiness_summary": {"ready_count": 1, "not_ready_count": 0, "governance_approval_gate_count": 1},
            "warnings": [],
        }


def test_packaging_governance_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "packaging_governance_service", lambda: _DummyPackagingService())

    assert module.packaging_governance(limit=5)["packaging_governance_status"] == "ok"
    assert module.packaging_governance_latest()["latest_packaging_governance"]["packaging_governance_id"] == "RFQ-PKG-001:packaging-governance"
    assert module.packaging_governance_history(limit=5)["count"] == 1
