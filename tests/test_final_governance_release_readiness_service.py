from __future__ import annotations

import importlib


class _DummyService:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __getattr__(self, name: str):
        if name == "latest" or name.startswith("latest_") or name.startswith("list_"):
            return lambda *args, **kwargs: self._payload
        raise AttributeError(name)


def _ready_payload() -> dict[str, object]:
    return {
        "status": "ok",
        "ready": True,
        "authority": "GO",
        "score": 96.0,
        "final_submission_readiness_status": "READY_TO_SUBMIT",
        "final_submission_readiness_score": 96.0,
        "final_escalation_authority": "operator_session",
        "executive_governance_index_status": "ok",
        "executive_governance_index_authority": "GO",
        "executive_governance_index_score": 96.0,
        "ready_for_controlled_rollout": True,
        "production_operationalization_status": "ok",
        "production_operationalization_authority": "GO",
        "production_operationalization_score": 96.0,
        "operator_access_governance_score": 96.0,
        "operator_access_governance": True,
        "active_supervision_coverage_ready": True,
        "supervision_command_status": "ok",
        "supervision_command_authority": "GO",
        "supervision_command_score": 96.0,
        "operations_audit_status": "ok",
        "operations_audit_authority": "GO",
        "operations_audit_score": 96.0,
        "incident_governance_status": "ok",
        "incident_governance_authority": "GO",
        "incident_governance_score": 96.0,
        "continuity_governance_status": "ok",
        "continuity_governance_authority": "GO",
        "continuity_governance_score": 96.0,
        "release_governance_status": "ok",
        "release_governance_authority": "GO",
        "release_governance_score": 96.0,
        "operational_pilot_status": "ok",
        "operational_pilot_authority": "GO",
        "operational_pilot_score": 96.0,
        "status": "ok",
        "stability_score": 96.0,
        "runtime_remediation_status": "ok",
        "runtime_remediation_authority": "GO",
        "runtime_remediation_score": 96.0,
        "ha_topology_status": "ok",
        "ha_topology_authority": "GO",
        "ha_topology_score": 96.0,
        "distributed_orchestration_status": "ok",
        "distributed_orchestration_authority": "GO",
        "distributed_orchestration_score": 96.0,
        "ingress_governance_status": "ok",
        "ingress_governance_authority": "GO",
        "ingress_governance_score": 96.0,
        "multi_tenant_governance_status": "ok",
        "multi_tenant_governance_authority": "GO",
        "multi_tenant_governance_score": 96.0,
        "distributed_observability_status": "ok",
        "distributed_observability_authority": "GO",
        "distributed_observability_score": 96.0,
        "autoscaling_governance_status": "ok",
        "autoscaling_governance_authority": "GO",
        "autoscaling_governance_score": 96.0,
        "backup_restore_governance_status": "ok",
        "backup_restore_governance_authority": "GO",
        "backup_restore_governance_score": 96.0,
        "disaster_recovery_governance_status": "ok",
        "disaster_recovery_governance_authority": "GO",
        "disaster_recovery_governance_score": 96.0,
        "live_cloud_credentials_present": False,
        "production_data_movement_enabled": False,
        "final_submission_readiness_status": "READY_TO_SUBMIT",
        "final_submission_readiness_score": 96.0,
        "final_escalation_authority": "operator_session",
        "ready": True,
        "tenant_data_residency_ready": True,
        "jurisdiction_boundary_ready": True,
        "cross_region_movement_restricted": True,
        "backup_residency_aligned": True,
        "audit_log_residency_aligned": True,
        "evidence_storage_residency_aligned": True,
        "sovereignty_escalation_ready": True,
        "restricted_region_blockers_clear": True,
        "regulatory_framework_readiness": True,
        "procurement_compliance_readiness": True,
        "audit_retention_readiness": True,
        "governance_evidence_completeness": True,
        "policy_exception_escalation_readiness": True,
        "compliance_review_supervision": True,
        "regulatory_blocker_visibility": True,
        "compliance_regulatory_governance_status": "ok",
        "compliance_regulatory_governance_authority": "GO",
        "compliance_regulatory_governance_score": 96.0,
        "warnings": [],
    }


def test_final_governance_release_readiness_service_ready_path() -> None:
    module = importlib.import_module("app.services.final_governance_release_readiness_service")
    service = module.FinalGovernanceReleaseReadinessService(
        final_readiness_service=_DummyService(_ready_payload()),
        executive_governance_index_service=_DummyService(_ready_payload()),
        production_operationalization_service=_DummyService(_ready_payload()),
        supervision_command_service=_DummyService(_ready_payload()),
        audit_service=_DummyService(_ready_payload()),
        incident_service=_DummyService(_ready_payload()),
        continuity_service=_DummyService(_ready_payload()),
        release_service=_DummyService(_ready_payload()),
        operational_pilot_service=_DummyService(_ready_payload()),
        operational_stability_service=_DummyService(_ready_payload()),
        runtime_remediation_service=_DummyService(_ready_payload()),
        distributed_orchestration_service=_DummyService(_ready_payload()),
        ha_topology_service=_DummyService(_ready_payload()),
        ingress_service=_DummyService(_ready_payload()),
        multi_tenant_service=_DummyService(_ready_payload()),
        distributed_observability_service=_DummyService(_ready_payload()),
        autoscaling_service=_DummyService(_ready_payload()),
        backup_restore_service=_DummyService(_ready_payload()),
        disaster_recovery_service=_DummyService(_ready_payload()),
        data_residency_service=_DummyService(_ready_payload()),
        compliance_regulatory_service=_DummyService(_ready_payload()),
        signature_service=_DummyService(_ready_payload()),
        activation_service=_DummyService(_ready_payload()),
        deadline_service=_DummyService(_ready_payload()),
    )

    latest = service.latest_final_governance_release_readiness()
    history = service.final_governance_release_readiness_history(limit=5)

    assert latest["final_governance_release_readiness_status"] == "ok"
    assert latest["final_governance_release_readiness_authority"] == "GO"
    assert latest["final_governance_release_readiness_score"] >= 90.0
    assert latest["unresolved_final_release_blockers"] == []
    assert latest["safety_boundaries"]["dry_run_enforced"] is True
    assert latest["safety_boundaries"]["human_supervision_required"] is True
    assert latest["safety_boundaries"]["final_automation_disabled"] is True
    assert latest["governance_command_centre_readiness"]["ready"] is True
    assert latest["compliance_regulatory_governance_readiness"]["ready"] is True
    assert history["count"] == 2
    assert history["final_governance_release_readiness_history"][0]["status"] == "ready"


def test_final_governance_release_readiness_service_blocked_path() -> None:
    module = importlib.import_module("app.services.final_governance_release_readiness_service")
    ready = _ready_payload()
    blocked = dict(ready)
    blocked["executive_governance_index_status"] = "blocked"
    blocked["executive_governance_index_authority"] = "NO_GO"
    blocked["executive_governance_index_score"] = 40.0
    blocked["status"] = "blocked"
    blocked["ready"] = False
    blocked["authority"] = "NO_GO"
    blocked["release_governance_status"] = "blocked"
    blocked["release_governance_authority"] = "NO_GO"
    blocked["release_governance_score"] = 40.0
    blocked["compliance_regulatory_governance_status"] = "blocked"
    blocked["compliance_regulatory_governance_authority"] = "NO_GO"
    blocked["compliance_regulatory_governance_score"] = 40.0

    service = module.FinalGovernanceReleaseReadinessService(
        final_readiness_service=_DummyService(blocked),
        executive_governance_index_service=_DummyService(blocked),
        production_operationalization_service=_DummyService(blocked),
        supervision_command_service=_DummyService(blocked),
        audit_service=_DummyService(blocked),
        incident_service=_DummyService(blocked),
        continuity_service=_DummyService(blocked),
        release_service=_DummyService(blocked),
        operational_pilot_service=_DummyService(blocked),
        operational_stability_service=_DummyService(blocked),
        runtime_remediation_service=_DummyService(blocked),
        distributed_orchestration_service=_DummyService(blocked),
        ha_topology_service=_DummyService(blocked),
        ingress_service=_DummyService(blocked),
        multi_tenant_service=_DummyService(blocked),
        distributed_observability_service=_DummyService(blocked),
        autoscaling_service=_DummyService(blocked),
        backup_restore_service=_DummyService(blocked),
        disaster_recovery_service=_DummyService(blocked),
        data_residency_service=_DummyService(blocked),
        compliance_regulatory_service=_DummyService(blocked),
        signature_service=_DummyService(blocked),
        activation_service=_DummyService(blocked),
        deadline_service=_DummyService(blocked),
    )

    latest = service.latest_final_governance_release_readiness()

    assert latest["final_governance_release_readiness_status"] == "blocked"
    assert latest["final_governance_release_readiness_authority"] == "NO_GO"
    assert latest["unresolved_final_release_blockers"]
    assert latest["warnings"]
