from __future__ import annotations

import importlib


class _DummyService:
    def list_disaster_recovery_governance(self, limit: int = 20):
        return {
            "status": "watch",
            "disaster_recovery_governance_status": "watch",
            "disaster_recovery_governance_authority": "WATCH",
            "disaster_recovery_governance_score": 79.0,
            "disaster_recovery_governance_grade": "watch",
            "recovery_state": "degraded-but-recovering",
            "latest_disaster_recovery_governance": {"analysis_id": "disaster-recovery-governance:latest"},
            "disaster_recovery_governance_history": [{"analysis_id": "disaster-recovery-governance:latest"}],
            "disaster_recovery_governance_history_summary": {
                "analysis_count": 1,
                "latest_analysis_id": "disaster-recovery-governance:latest",
                "latest_score": 79.0,
                "score_history": {"trend": "stable", "delta": 0.0, "average": 79.0, "latest": 79.0, "previous": 79.0, "points": [79.0]},
                "recovery_state_history": [[{"recovery_state": "degraded-but-recovering"}]],
            },
            "summary_counts": {"PASS": 0, "WARN": 1, "FAIL": 0},
            "warnings": ["regional failover recovery in progress"],
        }

    def latest_disaster_recovery_governance(self):
        return self.list_disaster_recovery_governance()

    def disaster_recovery_governance_history(self, limit: int = 20):
        payload = self.list_disaster_recovery_governance(limit=limit)
        return {
            "status": payload["status"],
            "disaster_recovery_governance_status": payload["disaster_recovery_governance_status"],
            "disaster_recovery_governance_authority": payload["disaster_recovery_governance_authority"],
            "disaster_recovery_governance_score": payload["disaster_recovery_governance_score"],
            "disaster_recovery_governance_grade": payload["disaster_recovery_governance_grade"],
            "count": len(payload["disaster_recovery_governance_history"]),
            "disaster_recovery_governance_history": payload["disaster_recovery_governance_history"],
            "disaster_recovery_governance_history_summary": payload["disaster_recovery_governance_history_summary"],
            "summary_counts": payload["summary_counts"],
            "warnings": payload["warnings"],
        }


def test_disaster_recovery_governance_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "disaster_recovery_governance_service", lambda: _DummyService())

    assert module.disaster_recovery_governance(limit=5)["disaster_recovery_governance_authority"] == "WATCH"
    assert module.disaster_recovery_governance_latest()["latest_disaster_recovery_governance"]["analysis_id"] == "disaster-recovery-governance:latest"
    assert module.disaster_recovery_governance_history(limit=5)["count"] == 1
