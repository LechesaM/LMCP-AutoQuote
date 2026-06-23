from __future__ import annotations

import importlib


class _DummyService:
    def list_executive_governance_index(self, limit: int = 20):
        return {
            "status": "ok",
            "executive_governance_index_status": "ok",
            "executive_governance_index_authority": "GO",
            "executive_governance_index_score": 94.0,
            "executive_governance_index_grade": "ready",
            "latest_executive_governance_index": {"analysis_id": "executive-governance-index:2026-06-24T12:00:00+00:00"},
            "executive_governance_index_history": [{"analysis_id": "executive-governance-index:2026-06-24T12:00:00+00:00"}],
            "executive_governance_index_history_summary": {"analysis_count": 1, "latest_analysis_id": "executive-governance-index:2026-06-24T12:00:00+00:00", "latest_score": 94.0, "score_history": {"trend": "stable", "delta": 0.0, "average": 94.0, "latest": 94.0, "previous": 94.0, "points": [94.0]}},
            "consolidated_governance_history": [{"analysis_id": "executive-governance-index:2026-06-24T12:00:00+00:00"}],
            "consolidated_governance_history_summary": {"analysis_count": 1},
            "summary_components": {"activation": 95.0},
            "warnings": [],
        }

    def latest_executive_governance_index(self):
        response = self.list_executive_governance_index()
        return {
            "status": response["status"],
            "executive_governance_index_status": response["executive_governance_index_status"],
            "executive_governance_index_authority": response["executive_governance_index_authority"],
            "executive_governance_index_score": response["executive_governance_index_score"],
            "executive_governance_index_grade": response["executive_governance_index_grade"],
            "latest_executive_governance_index": response["latest_executive_governance_index"],
            "executive_governance_index_history": response["executive_governance_index_history"],
            "executive_governance_index_history_summary": response["executive_governance_index_history_summary"],
            "consolidated_governance_history": response["consolidated_governance_history"],
            "consolidated_governance_history_summary": response["consolidated_governance_history_summary"],
            "summary_components": response["summary_components"],
            "warnings": response["warnings"],
        }

    def executive_governance_index_history(self, limit: int = 20):
        response = self.list_executive_governance_index(limit=limit)
        return {
            "status": response["status"],
            "count": len(response["executive_governance_index_history"]),
            "executive_governance_index_history": response["executive_governance_index_history"],
            "executive_governance_index_history_summary": response["executive_governance_index_history_summary"],
            "consolidated_governance_history": response["consolidated_governance_history"],
            "consolidated_governance_history_summary": response["consolidated_governance_history_summary"],
            "summary_components": response["summary_components"],
            "warnings": response["warnings"],
        }


def test_executive_governance_index_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "executive_governance_index_service", lambda: _DummyService())

    assert module.governance_index(limit=5)["executive_governance_index_status"] == "ok"
    assert module.governance_index_latest()["latest_executive_governance_index"]["analysis_id"] == "executive-governance-index:2026-06-24T12:00:00+00:00"
    assert module.governance_index_history(limit=5)["count"] == 1
