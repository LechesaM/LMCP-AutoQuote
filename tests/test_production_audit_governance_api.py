from __future__ import annotations

import importlib


class _DummyService:
    def list_operations_audit(self, limit: int = 20):
        return {
            "status": "ok",
            "operations_audit_status": "ok",
            "operations_audit_authority": "GO",
            "operations_audit_score": 96.0,
            "operations_audit_grade": "ready",
            "latest_operations_audit": {"analysis_id": "production-validation:operations-audit"},
            "operations_audit_history": [{"analysis_id": "production-validation:operations-audit"}],
            "operations_audit_history_summary": {"analysis_count": 1, "latest_analysis_id": "production-validation:operations-audit", "latest_score": 96.0, "score_history": {"trend": "stable", "delta": 0.0, "average": 96.0, "latest": 96.0, "previous": 96.0, "points": [96.0]}},
            "summary_counts": {"PASS": 8, "WARN": 0, "FAIL": 0},
            "warnings": [],
        }

    def latest_operations_audit(self):
        return self.list_operations_audit()

    def operations_audit_history(self, limit: int = 20):
        payload = self.list_operations_audit(limit=limit)
        return {
            "status": payload["status"],
            "operations_audit_status": payload["operations_audit_status"],
            "operations_audit_authority": payload["operations_audit_authority"],
            "operations_audit_score": payload["operations_audit_score"],
            "operations_audit_grade": payload["operations_audit_grade"],
            "count": len(payload["operations_audit_history"]),
            "operations_audit_history": payload["operations_audit_history"],
            "operations_audit_history_summary": payload["operations_audit_history_summary"],
            "summary_counts": payload["summary_counts"],
            "warnings": payload["warnings"],
        }


def test_production_audit_governance_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "production_audit_governance_service", lambda: _DummyService())

    assert module.operations_audit(limit=5)["operations_audit_authority"] == "GO"
    assert module.operations_audit_latest()["latest_operations_audit"]["analysis_id"] == "production-validation:operations-audit"
    assert module.operations_audit_history(limit=5)["count"] == 1
