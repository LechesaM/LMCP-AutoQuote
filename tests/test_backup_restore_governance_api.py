from __future__ import annotations

import importlib


class _DummyService:
    def list_backup_restore_governance(self, limit: int = 20):
        return {
            "status": "watch",
            "backup_restore_governance_status": "watch",
            "backup_restore_governance_authority": "WATCH",
            "backup_restore_governance_score": 77.0,
            "backup_restore_governance_grade": "watch",
            "recovery_state": "degraded-but-recovering",
            "latest_backup_restore_governance": {"analysis_id": "backup-restore-governance:latest"},
            "backup_governance_history": [{"analysis_id": "backup-restore-governance:latest"}],
            "backup_governance_history_summary": {
                "analysis_count": 1,
                "latest_analysis_id": "backup-restore-governance:latest",
                "latest_score": 77.0,
                "score_history": {"trend": "stable", "delta": 0.0, "average": 77.0, "latest": 77.0, "previous": 77.0, "points": [77.0]},
                "recovery_state_history": [[{"recovery_state": "degraded-but-recovering"}]],
            },
            "summary_counts": {"PASS": 0, "WARN": 1, "FAIL": 0},
            "warnings": ["restore rehearsal remains staged"],
        }

    def latest_backup_restore_governance(self):
        return self.list_backup_restore_governance()

    def backup_restore_governance_history(self, limit: int = 20):
        payload = self.list_backup_restore_governance(limit=limit)
        return {
            "status": payload["status"],
            "backup_restore_governance_status": payload["backup_restore_governance_status"],
            "backup_restore_governance_authority": payload["backup_restore_governance_authority"],
            "backup_restore_governance_score": payload["backup_restore_governance_score"],
            "backup_restore_governance_grade": payload["backup_restore_governance_grade"],
            "count": len(payload["backup_governance_history"]),
            "backup_governance_history": payload["backup_governance_history"],
            "backup_governance_history_summary": payload["backup_governance_history_summary"],
            "summary_counts": payload["summary_counts"],
            "warnings": payload["warnings"],
        }


def test_backup_restore_governance_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "backup_restore_governance_service", lambda: _DummyService())

    assert module.backup_restore_governance(limit=5)["backup_restore_governance_authority"] == "WATCH"
    assert module.backup_restore_governance_latest()["latest_backup_restore_governance"]["analysis_id"] == "backup-restore-governance:latest"
    assert module.backup_restore_governance_history(limit=5)["count"] == 1
