from __future__ import annotations

import importlib


class _DummyService:
    def list_distributed_orchestration(self, limit: int = 20):
        return {
            "status": "watch",
            "distributed_orchestration_status": "watch",
            "distributed_orchestration_authority": "WATCH",
            "distributed_orchestration_score": 79.0,
            "distributed_orchestration_grade": "watch",
            "recovery_state": "degraded-but-recovering",
            "latest_distributed_orchestration": {"analysis_id": "production-validation:distributed-orchestration"},
            "distributed_orchestration_history": [{"analysis_id": "production-validation:distributed-orchestration"}],
            "distributed_orchestration_history_summary": {"analysis_count": 1, "latest_analysis_id": "production-validation:distributed-orchestration", "latest_score": 79.0, "score_history": {"trend": "stable", "delta": 0.0, "average": 79.0, "latest": 79.0, "previous": 79.0, "points": [79.0]}},
            "summary_counts": {"PASS": 0, "WARN": 1, "FAIL": 0},
            "warnings": ["worker shard recovery in progress"],
        }

    def latest_distributed_orchestration(self):
        return self.list_distributed_orchestration()

    def distributed_orchestration_history(self, limit: int = 20):
        payload = self.list_distributed_orchestration(limit=limit)
        return {
            "status": payload["status"],
            "distributed_orchestration_status": payload["distributed_orchestration_status"],
            "distributed_orchestration_authority": payload["distributed_orchestration_authority"],
            "distributed_orchestration_score": payload["distributed_orchestration_score"],
            "distributed_orchestration_grade": payload["distributed_orchestration_grade"],
            "count": len(payload["distributed_orchestration_history"]),
            "distributed_orchestration_history": payload["distributed_orchestration_history"],
            "distributed_orchestration_history_summary": payload["distributed_orchestration_history_summary"],
            "summary_counts": payload["summary_counts"],
            "warnings": payload["warnings"],
        }


def test_distributed_orchestration_governance_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "distributed_orchestration_governance_service", lambda: _DummyService())

    assert module.distributed_orchestration(limit=5)["distributed_orchestration_authority"] == "WATCH"
    assert module.distributed_orchestration_latest()["latest_distributed_orchestration"]["analysis_id"] == "production-validation:distributed-orchestration"
    assert module.distributed_orchestration_history(limit=5)["count"] == 1
