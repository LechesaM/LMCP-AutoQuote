from __future__ import annotations

import importlib


class _DummyService:
    def list_ingress_governance(self, limit: int = 20):
        return {
            "status": "watch",
            "ingress_governance_status": "watch",
            "ingress_governance_authority": "WATCH",
            "ingress_governance_score": 78.0,
            "ingress_governance_grade": "watch",
            "recovery_state": "degraded-but-recovering",
            "latest_ingress_governance": {"analysis_id": "ingress-governance:latest"},
            "ingress_governance_history": [{"analysis_id": "ingress-governance:latest"}],
            "ingress_governance_history_summary": {
                "analysis_count": 1,
                "latest_analysis_id": "ingress-governance:latest",
                "latest_score": 78.0,
                "score_history": {"trend": "stable", "delta": 0.0, "average": 78.0, "latest": 78.0, "previous": 78.0, "points": [78.0]},
            },
            "summary_counts": {"PASS": 0, "WARN": 1, "FAIL": 0},
            "warnings": ["observability ingress remains internal-only"],
        }

    def latest_ingress_governance(self):
        return self.list_ingress_governance()

    def ingress_governance_history(self, limit: int = 20):
        payload = self.list_ingress_governance(limit=limit)
        return {
            "status": payload["status"],
            "ingress_governance_status": payload["ingress_governance_status"],
            "ingress_governance_authority": payload["ingress_governance_authority"],
            "ingress_governance_score": payload["ingress_governance_score"],
            "ingress_governance_grade": payload["ingress_governance_grade"],
            "count": len(payload["ingress_governance_history"]),
            "ingress_governance_history": payload["ingress_governance_history"],
            "ingress_governance_history_summary": payload["ingress_governance_history_summary"],
            "summary_counts": payload["summary_counts"],
            "warnings": payload["warnings"],
        }


def test_ingress_governance_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "ingress_governance_service", lambda: _DummyService())

    assert module.ingress_governance(limit=5)["ingress_governance_authority"] == "WATCH"
    assert module.ingress_governance_latest()["latest_ingress_governance"]["analysis_id"] == "ingress-governance:latest"
    assert module.ingress_governance_history(limit=5)["count"] == 1
