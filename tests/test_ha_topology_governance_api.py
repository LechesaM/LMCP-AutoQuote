from __future__ import annotations

import importlib


class _DummyService:
    def list_ha_topology(self, limit: int = 20):
        return {
            "status": "watch",
            "ha_topology_status": "watch",
            "ha_topology_authority": "WATCH",
            "ha_topology_score": 78.0,
            "ha_topology_grade": "watch",
            "latest_ha_topology": {"analysis_id": "production-governance:ha-topology"},
            "ha_topology_history": [{"analysis_id": "production-governance:ha-topology"}],
            "ha_topology_history_summary": {"analysis_count": 1, "latest_analysis_id": "production-governance:ha-topology", "latest_score": 78.0, "score_history": {"trend": "stable", "delta": 0.0, "average": 78.0, "latest": 78.0, "previous": 78.0, "points": [78.0]}},
            "summary_counts": {"PASS": 0, "WARN": 7, "FAIL": 0},
            "warnings": ["Redis HA readiness is not yet complete."],
        }

    def latest_ha_topology(self):
        return self.list_ha_topology()

    def ha_topology_history(self, limit: int = 20):
        payload = self.list_ha_topology(limit=limit)
        return {
            "status": payload["status"],
            "ha_topology_status": payload["ha_topology_status"],
            "ha_topology_authority": payload["ha_topology_authority"],
            "ha_topology_score": payload["ha_topology_score"],
            "ha_topology_grade": payload["ha_topology_grade"],
            "count": len(payload["ha_topology_history"]),
            "ha_topology_history": payload["ha_topology_history"],
            "ha_topology_history_summary": payload["ha_topology_history_summary"],
            "summary_counts": payload["summary_counts"],
            "warnings": payload["warnings"],
        }


def test_ha_topology_governance_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "ha_topology_governance_service", lambda: _DummyService())

    assert module.ha_topology(limit=5)["ha_topology_authority"] == "WATCH"
    assert module.ha_topology_latest()["latest_ha_topology"]["analysis_id"] == "production-governance:ha-topology"
    assert module.ha_topology_history(limit=5)["count"] == 1
