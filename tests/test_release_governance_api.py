from __future__ import annotations

import importlib


class _DummyService:
    def list_release_governance(self, limit: int = 20):
        return {
            "status": "ok",
            "release_governance_status": "ok",
            "release_governance_authority": "GO",
            "release_governance_score": 96.0,
            "release_governance_grade": "ready",
            "production_rollout_readiness": True,
            "production_rollout_readiness_status": "ready",
            "latest_release_governance": {"analysis_id": "production-validation:release-gate"},
            "release_governance_history": [{"analysis_id": "production-validation:release-gate"}],
            "release_governance_history_summary": {"analysis_count": 1, "latest_analysis_id": "production-validation:release-gate", "latest_score": 96.0},
            "deployment_risk_indicators": {"deployment_risk": False},
            "operational_release_indicators": {"submission_lock_verified": True},
            "release_readiness_indicators": {"runtime_segmentation_ready": True},
            "release_authority_indicators": {"go_release_authority": True, "watch_release_authority": False, "no_go_release_authority": False, "active_authority": "GO"},
            "unresolved_deployment_blockers": [],
            "governance_override_authority": False,
            "release_escalation_authority": False,
            "summary_components": {"runtime_segmentation": 96.0},
            "warnings": [],
        }

    def latest_release_governance(self):
        return {
            "status": "ok",
            "release_governance_status": "ok",
            "release_governance_authority": "GO",
            "release_governance_score": 96.0,
            "release_governance_grade": "ready",
            "production_rollout_readiness": True,
            "production_rollout_readiness_status": "ready",
            "latest_release_governance": {"analysis_id": "production-validation:release-gate"},
            "release_governance_history": [{"analysis_id": "production-validation:release-gate"}],
            "release_governance_history_summary": {"analysis_count": 1, "latest_analysis_id": "production-validation:release-gate", "latest_score": 96.0},
            "deployment_risk_indicators": {"deployment_risk": False},
            "operational_release_indicators": {"submission_lock_verified": True},
            "release_readiness_indicators": {"runtime_segmentation_ready": True},
            "release_authority_indicators": {"go_release_authority": True, "watch_release_authority": False, "no_go_release_authority": False, "active_authority": "GO"},
            "unresolved_deployment_blockers": [],
            "governance_override_authority": False,
            "release_escalation_authority": False,
            "summary_components": {"runtime_segmentation": 96.0},
            "warnings": [],
        }

    def release_governance_history(self, limit: int = 20):
        return {
            "status": "ok",
            "count": 1,
            "release_governance_history": [{"analysis_id": "production-validation:release-gate"}],
            "release_governance_history_summary": {"analysis_count": 1, "latest_analysis_id": "production-validation:release-gate", "latest_score": 96.0},
            "deployment_risk_indicators": {"deployment_risk": False},
            "operational_release_indicators": {"submission_lock_verified": True},
            "release_readiness_indicators": {"runtime_segmentation_ready": True},
            "release_authority_indicators": {"go_release_authority": True, "watch_release_authority": False, "no_go_release_authority": False, "active_authority": "GO"},
            "unresolved_deployment_blockers": [],
            "governance_override_authority": False,
            "release_escalation_authority": False,
            "production_rollout_readiness": True,
            "production_rollout_readiness_status": "ready",
            "summary_components": {"runtime_segmentation": 96.0},
            "warnings": [],
        }


def test_release_governance_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "release_governance_service", lambda: _DummyService())

    assert module.release_governance(limit=5)["release_governance_authority"] == "GO"
    assert module.release_governance_latest()["latest_release_governance"]["analysis_id"] == "production-validation:release-gate"
    assert module.release_governance_history(limit=5)["count"] == 1
