from __future__ import annotations

import importlib


class _DummyService:
    def list_operational_intelligence(self, limit: int = 20):
        return {
            "status": "ok",
            "operational_intelligence_status": "ok",
            "operational_intelligence_score": 95.0,
            "latest_operational_intelligence": {"analysis_id": "lifecycle:intelligence:2026-06-23T00:00:00+00:00"},
            "operational_intelligence_history": [{"analysis_id": "cycle-1:intelligence"}],
            "operational_intelligence_history_summary": {"analysis_count": 1},
            "summary_components": {"rfq_trend": 95.0},
            "warnings": [],
        }

    def latest_operational_intelligence(self):
        return {
            "status": "ok",
            "operational_intelligence_status": "ok",
            "operational_intelligence_score": 95.0,
            "latest_operational_intelligence": {"analysis_id": "lifecycle:intelligence:2026-06-23T00:00:00+00:00"},
            "operational_intelligence_history": [{"analysis_id": "cycle-1:intelligence"}],
            "operational_intelligence_history_summary": {"analysis_count": 1},
            "summary_components": {"rfq_trend": 95.0},
            "warnings": [],
        }

    def operational_intelligence_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "operational_intelligence_history": [{"analysis_id": "cycle-1:intelligence"}],
            "operational_intelligence_history_summary": {"analysis_count": 1},
            "summary_components": {"rfq_trend": 95.0},
            "warnings": [],
        }


def test_operational_intelligence_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "operational_intelligence_service", lambda: _DummyService())

    assert module.operational_intelligence(limit=5)["operational_intelligence_status"] == "ok"
    assert module.operational_intelligence_latest()["latest_operational_intelligence"]["analysis_id"] == "lifecycle:intelligence:2026-06-23T00:00:00+00:00"
    assert module.operational_intelligence_history(limit=5)["count"] == 1
