from __future__ import annotations

import importlib


class _DummyService:
    def list_activation_governance(self, limit: int = 20):
        return {
            "status": "ok",
            "activation_governance_status": "ok",
            "activation_governance_authority": "GO",
            "activation_governance_score": 96.0,
            "activation_governance_grade": "ready",
            "production_rollout_readiness": True,
            "production_rollout_readiness_status": "ready",
            "latest_activation_governance": {"analysis_id": "production-validation:activation-governance"},
            "activation_governance_history": [{"analysis_id": "production-validation:activation-governance"}],
            "activation_governance_history_summary": {"analysis_count": 1, "latest_analysis_id": "production-validation:activation-governance", "latest_score": 96.0, "score_history": {"trend": "stable", "delta": 0.0, "average": 96.0, "latest": 96.0, "previous": 96.0, "points": [96.0]}},
            "tenant_activation_readiness": {"tenant_activation_ready": True},
            "operator_certification_readiness": {"operator_certification_ready": True},
            "supervision_assignment_readiness": {"supervision_assignment_ready": True},
            "staged_rollout_segmentation": {"staged_rollout_segmentation_ready": True},
            "throughput_expansion_readiness": {"throughput_expansion_ready": True},
            "rollout_freeze_indicators": {"freeze_active": False},
            "escalation_readiness": {"escalation_ready": True},
            "operator_saturation_indicators": {"operator_saturation_active": False},
            "supervision_coverage_indicators": {"active_supervision_coverage_ready": True},
            "rollout_expansion_history": [{"analysis_id": "production-validation:activation-governance"}],
            "rollout_expansion_history_summary": {"analysis_count": 1, "latest_analysis_id": "production-validation:activation-governance", "latest_score": 96.0, "score_history": {"trend": "stable", "delta": 0.0, "average": 96.0, "latest": 96.0, "previous": 96.0, "points": [96.0]}},
            "deployment_health_summary": {"deployment_health_ready": True},
            "production_observability_summary": {"production_observability_ready": True},
            "institutional_rollout_certification_evidence": {"rollout_ready_for_supervised_deployment": True},
            "latest_release_certification": {"release_authority": "GO"},
            "release_certification_snapshot": {"release_authority_certification": {"active_authority": "GO"}},
            "source_artifacts": {"rollout_validation": "production_rollout_validation.json"},
            "source_runtime": {"environment": "staging"},
            "summary_counts": {"PASS": 8, "WARN": 0, "FAIL": 0},
            "warnings": [],
        }

    def latest_activation_governance(self):
        return self.list_activation_governance()

    def activation_governance_history(self, limit: int = 20):
        payload = self.list_activation_governance(limit=limit)
        return {
            "status": payload["status"],
            "count": len(payload["activation_governance_history"]),
            "activation_governance_history": payload["activation_governance_history"],
            "activation_governance_history_summary": payload["activation_governance_history_summary"],
            "production_rollout_readiness": payload["production_rollout_readiness"],
            "production_rollout_readiness_status": payload["production_rollout_readiness_status"],
            "rollout_freeze_indicators": payload["rollout_freeze_indicators"],
            "escalation_readiness": payload["escalation_readiness"],
            "operator_saturation_indicators": payload["operator_saturation_indicators"],
            "supervision_coverage_indicators": payload["supervision_coverage_indicators"],
            "warnings": payload["warnings"],
        }


def test_activation_governance_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "activation_governance_service", lambda: _DummyService())

    assert module.activation_governance(limit=5)["activation_governance_authority"] == "GO"
    assert module.activation_governance_latest()["latest_activation_governance"]["analysis_id"] == "production-validation:activation-governance"
    assert module.activation_governance_history(limit=5)["count"] == 1
