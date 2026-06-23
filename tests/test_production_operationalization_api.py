from __future__ import annotations

import importlib


class _DummyService:
    def list_production_governance(self, limit: int = 20):
        return {
            "status": "ok",
            "production_readiness_status": "ok",
            "production_readiness_score": 94.0,
            "latest_production_governance": {"analysis_id": "production-governance:2026-06-23T00:00:00+00:00"},
            "production_governance_history": [{"analysis_id": "cycle-1:production"}],
            "production_governance_history_summary": {"analysis_count": 1},
            "summary_components": {"deployment_readiness": 94.0},
            "warnings": [],
        }

    def latest_production_governance(self):
        return {
            "status": "ok",
            "production_readiness_status": "ok",
            "production_readiness_score": 94.0,
            "latest_production_governance": {"analysis_id": "production-governance:2026-06-23T00:00:00+00:00"},
            "production_governance_history": [{"analysis_id": "cycle-1:production"}],
            "production_governance_history_summary": {"analysis_count": 1},
            "summary_components": {"deployment_readiness": 94.0},
            "warnings": [],
        }

    def production_governance_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "production_governance_history": [{"analysis_id": "cycle-1:production"}],
            "production_governance_history_summary": {"analysis_count": 1},
            "summary_components": {"deployment_readiness": 94.0},
            "warnings": [],
        }


def test_production_operationalization_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "production_operationalization_service", lambda: _DummyService())

    assert module.production_governance(limit=5)["production_readiness_status"] == "ok"
    assert module.production_governance_latest()["latest_production_governance"]["analysis_id"] == "production-governance:2026-06-23T00:00:00+00:00"
    assert module.production_governance_history(limit=5)["count"] == 1
