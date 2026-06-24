from __future__ import annotations

import importlib


class _DummyService:
    def list_multi_tenant_governance(self, limit: int = 20):
        return {
            "status": "watch",
            "multi_tenant_governance_status": "watch",
            "multi_tenant_governance_authority": "WATCH",
            "multi_tenant_governance_score": 79.0,
            "multi_tenant_governance_grade": "watch",
            "recovery_state": "degraded-but-recovering",
            "latest_multi_tenant_governance": {"analysis_id": "multi-tenant-governance:latest"},
            "multi_tenant_governance_history": [{"analysis_id": "multi-tenant-governance:latest"}],
            "multi_tenant_governance_history_summary": {
                "analysis_count": 1,
                "latest_analysis_id": "multi-tenant-governance:latest",
                "latest_score": 79.0,
                "score_history": {"trend": "stable", "delta": 0.0, "average": 79.0, "latest": 79.0, "previous": 79.0, "points": [79.0]},
            },
            "summary_counts": {"PASS": 0, "WARN": 1, "FAIL": 0},
            "warnings": ["tenant workload separation remains in progress"],
        }

    def latest_multi_tenant_governance(self):
        return self.list_multi_tenant_governance()

    def multi_tenant_governance_history(self, limit: int = 20):
        payload = self.list_multi_tenant_governance(limit=limit)
        return {
            "status": payload["status"],
            "multi_tenant_governance_status": payload["multi_tenant_governance_status"],
            "multi_tenant_governance_authority": payload["multi_tenant_governance_authority"],
            "multi_tenant_governance_score": payload["multi_tenant_governance_score"],
            "multi_tenant_governance_grade": payload["multi_tenant_governance_grade"],
            "count": len(payload["multi_tenant_governance_history"]),
            "multi_tenant_governance_history": payload["multi_tenant_governance_history"],
            "multi_tenant_governance_history_summary": payload["multi_tenant_governance_history_summary"],
            "summary_counts": payload["summary_counts"],
            "warnings": payload["warnings"],
        }


def test_multi_tenant_governance_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "multi_tenant_governance_service", lambda: _DummyService())

    assert module.multi_tenant_governance(limit=5)["multi_tenant_governance_authority"] == "WATCH"
    assert module.multi_tenant_governance_latest()["latest_multi_tenant_governance"]["analysis_id"] == "multi-tenant-governance:latest"
    assert module.multi_tenant_governance_history(limit=5)["count"] == 1
