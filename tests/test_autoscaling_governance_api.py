from __future__ import annotations

import importlib


class _DummyService:
    def list_autoscaling_governance(self, limit: int = 20):
        return {
            "status": "watch",
            "autoscaling_governance_status": "watch",
            "autoscaling_governance_authority": "WATCH",
            "autoscaling_governance_score": 78.5,
            "autoscaling_governance_grade": "watch",
            "recovery_state": "degraded-but-recovering",
            "latest_autoscaling_governance": {"analysis_id": "autoscaling-governance:latest"},
            "autoscaling_governance_history": [{"analysis_id": "autoscaling-governance:latest"}],
            "autoscaling_governance_history_summary": {
                "analysis_count": 1,
                "latest_analysis_id": "autoscaling-governance:latest",
                "latest_score": 78.5,
                "score_history": {"trend": "stable", "delta": 0.0, "average": 78.5, "latest": 78.5, "previous": 78.5, "points": [78.5]},
                "recovery_state_history": [[{"recovery_state": "degraded-but-recovering"}]],
            },
            "summary_counts": {"PASS": 0, "WARN": 1, "FAIL": 0},
            "warnings": ["queue-depth scaling remains staged"],
        }

    def latest_autoscaling_governance(self):
        return self.list_autoscaling_governance()

    def autoscaling_governance_history(self, limit: int = 20):
        payload = self.list_autoscaling_governance(limit=limit)
        return {
            "status": payload["status"],
            "autoscaling_governance_status": payload["autoscaling_governance_status"],
            "autoscaling_governance_authority": payload["autoscaling_governance_authority"],
            "autoscaling_governance_score": payload["autoscaling_governance_score"],
            "autoscaling_governance_grade": payload["autoscaling_governance_grade"],
            "count": len(payload["autoscaling_governance_history"]),
            "autoscaling_governance_history": payload["autoscaling_governance_history"],
            "autoscaling_governance_history_summary": payload["autoscaling_governance_history_summary"],
            "summary_counts": payload["summary_counts"],
            "warnings": payload["warnings"],
        }


def test_autoscaling_governance_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "autoscaling_governance_service", lambda: _DummyService())

    assert module.autoscaling_governance(limit=5)["autoscaling_governance_authority"] == "WATCH"
    assert module.autoscaling_governance_latest()["latest_autoscaling_governance"]["analysis_id"] == "autoscaling-governance:latest"
    assert module.autoscaling_governance_history(limit=5)["count"] == 1
