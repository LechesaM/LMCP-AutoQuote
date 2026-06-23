from __future__ import annotations

import importlib


class _DummyService:
    def list_executive_command(self, limit: int = 20):
        return {
            "status": "ok",
            "executive_governance_status": "ok",
            "executive_governance_score": 94.0,
            "latest_executive_intelligence": {"analysis_id": "executive-command:2026-06-23T00:00:00+00:00"},
            "executive_intelligence_history": [{"analysis_id": "cycle-1:executive"}],
            "executive_intelligence_history_summary": {"analysis_count": 1},
            "summary_components": {"procurement_health_score": 94.0},
            "warnings": [],
        }

    def latest_executive_command(self):
        return {
            "status": "ok",
            "executive_governance_status": "ok",
            "executive_governance_score": 94.0,
            "latest_executive_intelligence": {"analysis_id": "executive-command:2026-06-23T00:00:00+00:00"},
            "executive_intelligence_history": [{"analysis_id": "cycle-1:executive"}],
            "executive_intelligence_history_summary": {"analysis_count": 1},
            "summary_components": {"procurement_health_score": 94.0},
            "warnings": [],
        }

    def executive_command_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "executive_intelligence_history": [{"analysis_id": "cycle-1:executive"}],
            "executive_intelligence_history_summary": {"analysis_count": 1},
            "summary_components": {"procurement_health_score": 94.0},
            "warnings": [],
        }


def test_executive_command_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "executive_command_service", lambda: _DummyService())

    assert module.executive_command(limit=5)["executive_governance_status"] == "ok"
    assert module.executive_command_latest()["latest_executive_intelligence"]["analysis_id"] == "executive-command:2026-06-23T00:00:00+00:00"
    assert module.executive_command_history(limit=5)["count"] == 1
