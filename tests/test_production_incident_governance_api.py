from __future__ import annotations

import importlib


class _DummyService:
    def list_incident_governance(self, limit: int = 20):
        return {
            "status": "ok",
            "incident_governance_status": "ok",
            "incident_governance_authority": "GO",
            "incident_governance_score": 96.0,
            "incident_governance_grade": "ready",
            "latest_incident_governance": {"analysis_id": "production-validation:incident-governance"},
            "incident_governance_history": [{"analysis_id": "production-validation:incident-governance"}],
            "incident_governance_history_summary": {"analysis_count": 1, "latest_analysis_id": "production-validation:incident-governance", "latest_score": 96.0, "score_history": {"trend": "stable", "delta": 0.0, "average": 96.0, "latest": 96.0, "previous": 96.0, "points": [96.0]}},
            "summary_counts": {"PASS": 8, "WARN": 0, "FAIL": 0},
            "warnings": [],
        }

    def latest_incident_governance(self):
        return self.list_incident_governance()

    def incident_governance_history(self, limit: int = 20):
        payload = self.list_incident_governance(limit=limit)
        return {
            "status": payload["status"],
            "incident_governance_status": payload["incident_governance_status"],
            "incident_governance_authority": payload["incident_governance_authority"],
            "incident_governance_score": payload["incident_governance_score"],
            "incident_governance_grade": payload["incident_governance_grade"],
            "count": len(payload["incident_governance_history"]),
            "incident_governance_history": payload["incident_governance_history"],
            "incident_governance_history_summary": payload["incident_governance_history_summary"],
            "summary_counts": payload["summary_counts"],
            "warnings": payload["warnings"],
        }


def test_production_incident_governance_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "production_incident_governance_service", lambda: _DummyService())

    assert module.incident_governance(limit=5)["incident_governance_authority"] == "GO"
    assert module.incident_governance_latest()["latest_incident_governance"]["analysis_id"] == "production-validation:incident-governance"
    assert module.incident_governance_history(limit=5)["count"] == 1
