from __future__ import annotations

import importlib


class _DummyService:
    def list_continuity_governance(self, limit: int = 20):
        return {
            "status": "ok",
            "continuity_governance_status": "ok",
            "continuity_governance_authority": "GO",
            "continuity_governance_score": 96.0,
            "continuity_governance_grade": "ready",
            "latest_continuity_governance": {"analysis_id": "production-validation:continuity-governance"},
            "continuity_governance_history": [{"analysis_id": "production-validation:continuity-governance"}],
            "continuity_governance_history_summary": {"analysis_count": 1, "latest_analysis_id": "production-validation:continuity-governance", "latest_score": 96.0, "score_history": {"trend": "stable", "delta": 0.0, "average": 96.0, "latest": 96.0, "previous": 96.0, "points": [96.0]}},
            "summary_counts": {"PASS": 8, "WARN": 0, "FAIL": 0},
            "warnings": [],
        }

    def latest_continuity_governance(self):
        return self.list_continuity_governance()

    def continuity_governance_history(self, limit: int = 20):
        payload = self.list_continuity_governance(limit=limit)
        return {
            "status": payload["status"],
            "continuity_governance_status": payload["continuity_governance_status"],
            "continuity_governance_authority": payload["continuity_governance_authority"],
            "continuity_governance_score": payload["continuity_governance_score"],
            "continuity_governance_grade": payload["continuity_governance_grade"],
            "count": len(payload["continuity_governance_history"]),
            "continuity_governance_history": payload["continuity_governance_history"],
            "continuity_governance_history_summary": payload["continuity_governance_history_summary"],
            "summary_counts": payload["summary_counts"],
            "warnings": payload["warnings"],
        }


def test_production_continuity_governance_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "production_continuity_governance_service", lambda: _DummyService())

    assert module.continuity_governance(limit=5)["continuity_governance_authority"] == "GO"
    assert module.continuity_governance_latest()["latest_continuity_governance"]["analysis_id"] == "production-validation:continuity-governance"
    assert module.continuity_governance_history(limit=5)["count"] == 1
