from __future__ import annotations

import importlib


class _DummyService:
    def list_supervision_command(self, limit: int = 20):
        return {
            "status": "ok",
            "supervision_command_status": "ok",
            "supervision_command_authority": "GO",
            "supervision_command_score": 96.0,
            "supervision_command_grade": "ready",
            "production_rollout_readiness": True,
            "production_rollout_readiness_status": "ready",
            "latest_supervision_command": {"analysis_id": "production-validation:supervision-command"},
            "supervision_governance_history": [{"analysis_id": "production-validation:supervision-command"}],
            "supervision_governance_history_summary": {"analysis_count": 1, "latest_analysis_id": "production-validation:supervision-command", "latest_score": 96.0, "score_history": {"trend": "stable", "delta": 0.0, "average": 96.0, "latest": 96.0, "previous": 96.0, "points": [96.0]}},
            "active_supervised_operators": [{"operator_name": "staging-governance-operator"}],
            "supervision_coverage": {"supervision_coverage_ready": True, "coverage_score": 96.0},
            "active_rfq_oversight": {"assigned_rfq_count": 1, "pending_approval_count": 0},
            "escalation_command_visibility": {"escalation_ready": True, "review_board_status": "watch"},
            "supervision_saturation": {"supervision_saturation_active": False},
            "supervision_lapse_indicators": {"coverage_lapse": False},
            "operational_workload_visibility": {"workload_pressure": "low"},
            "supervision_sla_visibility": {"sla_ready": True},
            "operational_freeze_indicators": {"freeze_active": False},
            "latest_rollout_validation": {"validation_id": "production-validation"},
            "latest_release_certification": {"release_authority": "GO"},
            "release_certification_snapshot": {"release_authority_certification": {"active_authority": "GO"}},
            "deployment_health_summary": {"deployment_health_ready": True},
            "production_observability_summary": {"production_observability_ready": True},
            "institutional_rollout_certification_evidence": {"rollout_ready_for_supervised_deployment": True},
            "rollout_readiness_summary": {"rollout_readiness_score": 96.0},
            "operator_onboarding_readiness_summary": {"operator_name": "staging-governance-operator"},
            "summary_counts": {"PASS": 8, "WARN": 0, "FAIL": 0},
            "warnings": [],
        }

    def latest_supervision_command(self):
        return self.list_supervision_command()

    def supervision_command_history(self, limit: int = 20):
        payload = self.list_supervision_command(limit=limit)
        return {
            "status": payload["status"],
            "count": len(payload["supervision_governance_history"]),
            "supervision_governance_history": payload["supervision_governance_history"],
            "supervision_governance_history_summary": payload["supervision_governance_history_summary"],
            "production_rollout_readiness": payload["production_rollout_readiness"],
            "production_rollout_readiness_status": payload["production_rollout_readiness_status"],
            "supervision_saturation": payload["supervision_saturation"],
            "supervision_lapse_indicators": payload["supervision_lapse_indicators"],
            "operational_freeze_indicators": payload["operational_freeze_indicators"],
            "warnings": payload["warnings"],
        }


def test_production_supervision_command_routes_expose_read_only_governance(monkeypatch) -> None:
    module = importlib.import_module("app.api.rfq_lifecycle_api")
    monkeypatch.setattr(module, "supervision_command_service", lambda: _DummyService())

    assert module.supervision_command(limit=5)["supervision_command_authority"] == "GO"
    assert module.supervision_command_latest()["latest_supervision_command"]["analysis_id"] == "production-validation:supervision-command"
    assert module.supervision_command_history(limit=5)["count"] == 1
