from __future__ import annotations

import importlib


class _DummyService:
    def list_final_governance_release_readiness(self, limit: int = 20):
        return {
            "status": "ok",
            "final_governance_release_readiness_status": "ok",
            "final_governance_release_readiness_authority": "GO",
            "final_governance_release_readiness_score": 96.0,
            "final_governance_release_readiness_grade": "ready",
            "latest_final_governance_release_readiness": {"final_governance_release_readiness_id": "final-governance-release-readiness:latest"},
            "final_governance_release_readiness_history": [{"final_governance_release_readiness_id": "final-governance-release-readiness:latest"}],
            "final_governance_release_readiness_history_summary": {"history_count": 1},
            "summary_counts": {"PASS": 1, "WARN": 0, "FAIL": 0},
            "warnings": [],
        }

    def latest_final_governance_release_readiness(self):
        return self.list_final_governance_release_readiness()

    def final_governance_release_readiness_history(self, limit: int = 20):
        payload = self.list_final_governance_release_readiness(limit=limit)
        return {
            "status": payload["status"],
            "environment": "staging",
            "governance_mode": "read_only",
            "count": len(payload["final_governance_release_readiness_history"]),
            "final_governance_release_readiness_history": payload["final_governance_release_readiness_history"],
            "warnings": payload["warnings"],
        }


def test_final_governance_release_readiness_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "final_governance_release_readiness_service", lambda: _DummyService())

    assert module.final_governance_release_readiness(limit=5)["final_governance_release_readiness_authority"] == "GO"
    assert module.final_governance_release_readiness_latest()["latest_final_governance_release_readiness"]["final_governance_release_readiness_id"] == "final-governance-release-readiness:latest"
    assert module.final_governance_release_readiness_history(limit=5)["count"] == 1
