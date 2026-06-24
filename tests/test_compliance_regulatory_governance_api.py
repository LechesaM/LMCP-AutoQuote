from __future__ import annotations

import importlib


class _DummyService:
    def list_compliance_regulatory_governance(self, limit: int = 20):
        return {
            "status": "watch",
            "compliance_regulatory_governance_status": "watch",
            "compliance_regulatory_governance_authority": "WATCH",
            "compliance_regulatory_governance_score": 79.0,
            "compliance_regulatory_governance_grade": "watch",
            "recovery_state": "degraded-but-recovering",
            "latest_compliance_regulatory_governance": {"analysis_id": "compliance-regulatory-governance:latest"},
            "compliance_regulatory_governance_history": [{"analysis_id": "compliance-regulatory-governance:latest"}],
            "summary_counts": {"PASS": 0, "WARN": 1, "FAIL": 0},
            "warnings": ["policy exception review remains in progress"],
        }

    def latest_compliance_regulatory_governance(self):
        return self.list_compliance_regulatory_governance()

    def compliance_regulatory_governance_history(self, limit: int = 20):
        payload = self.list_compliance_regulatory_governance(limit=limit)
        return {
            "status": payload["status"],
            "compliance_regulatory_governance_status": payload["compliance_regulatory_governance_status"],
            "compliance_regulatory_governance_authority": payload["compliance_regulatory_governance_authority"],
            "compliance_regulatory_governance_score": payload["compliance_regulatory_governance_score"],
            "compliance_regulatory_governance_grade": payload["compliance_regulatory_governance_grade"],
            "count": len(payload["compliance_regulatory_governance_history"]),
            "history": payload["compliance_regulatory_governance_history"],
            "summary_counts": payload["summary_counts"],
            "warnings": payload["warnings"],
        }


def test_compliance_regulatory_governance_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "compliance_regulatory_governance_service", lambda: _DummyService())

    assert module.compliance_regulatory_governance(limit=5)["compliance_regulatory_governance_authority"] == "WATCH"
    assert module.compliance_regulatory_governance_latest()["latest_compliance_regulatory_governance"]["analysis_id"] == "compliance-regulatory-governance:latest"
    assert module.compliance_regulatory_governance_history(limit=5)["count"] == 1
