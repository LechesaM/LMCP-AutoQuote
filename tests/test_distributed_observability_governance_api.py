from __future__ import annotations

import importlib


class _DummyService:
    def list_distributed_observability(self, limit: int = 20):
        return {
            "status": "watch",
            "distributed_observability_status": "watch",
            "distributed_observability_authority": "WATCH",
            "distributed_observability_score": 79.0,
            "distributed_observability_grade": "watch",
            "recovery_state": "degraded-but-recovering",
            "latest_distributed_observability": {"analysis_id": "distributed-observability:latest"},
            "distributed_observability_history": [{"analysis_id": "distributed-observability:latest"}],
            "distributed_observability_history_summary": {
                "analysis_count": 1,
                "latest_analysis_id": "distributed-observability:latest",
                "latest_score": 79.0,
                "score_history": {"trend": "stable", "delta": 0.0, "average": 79.0, "latest": 79.0, "previous": 79.0, "points": [79.0]},
            },
            "summary_counts": {"PASS": 0, "WARN": 1, "FAIL": 0},
            "warnings": ["distributed metrics readiness remains in progress"],
        }

    def latest_distributed_observability(self):
        return self.list_distributed_observability()

    def distributed_observability_history(self, limit: int = 20):
        payload = self.list_distributed_observability(limit=limit)
        return {
            "status": payload["status"],
            "distributed_observability_status": payload["distributed_observability_status"],
            "distributed_observability_authority": payload["distributed_observability_authority"],
            "distributed_observability_score": payload["distributed_observability_score"],
            "distributed_observability_grade": payload["distributed_observability_grade"],
            "count": len(payload["distributed_observability_history"]),
            "distributed_observability_history": payload["distributed_observability_history"],
            "distributed_observability_history_summary": payload["distributed_observability_history_summary"],
            "summary_counts": payload["summary_counts"],
            "warnings": payload["warnings"],
        }


def test_distributed_observability_governance_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "distributed_observability_governance_service", lambda: _DummyService())

    assert module.distributed_observability(limit=5)["distributed_observability_authority"] == "WATCH"
    assert module.distributed_observability_latest()["latest_distributed_observability"]["analysis_id"] == "distributed-observability:latest"
    assert module.distributed_observability_history(limit=5)["count"] == 1
