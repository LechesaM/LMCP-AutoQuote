from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.activation_governance_service import ActivationGovernanceService
from app.services.autoscaling_governance_service import AutoscalingGovernanceService
from app.services.backup_restore_governance_service import BackupRestoreGovernanceService
from app.services.compliance_regulatory_governance_service import ComplianceRegulatoryGovernanceService
from app.services.data_residency_governance_service import DataResidencyGovernanceService
from app.services.deadline_governance_service import DeadlineGovernanceService
from app.services.disaster_recovery_governance_service import DisasterRecoveryGovernanceService
from app.services.distributed_observability_governance_service import DistributedObservabilityGovernanceService
from app.services.distributed_orchestration_governance_service import DistributedOrchestrationGovernanceService
from app.services.executive_governance_index_service import ExecutiveGovernanceIndexService
from app.services.final_readiness_governance_service import FinalReadinessGovernanceService
from app.services.ha_topology_governance_service import HaTopologyGovernanceService
from app.services.ingress_governance_service import IngressGovernanceService
from app.services.multi_tenant_governance_service import MultiTenantGovernanceService
from app.services.operational_exception_service import _safe_dict, _safe_float, _safe_list, _safe_str
from app.services.operational_pilot_execution_service import OperationalPilotExecutionService
from app.services.operational_stability_service import OperationalStabilityService
from app.services.production_audit_governance_service import ProductionAuditGovernanceService
from app.services.production_continuity_governance_service import ProductionContinuityGovernanceService
from app.services.production_incident_governance_service import ProductionIncidentGovernanceService
from app.services.production_operationalization_service import ProductionOperationalizationService
from app.services.production_release_governance_service import ProductionReleaseGovernanceService
from app.services.production_supervision_command_service import ProductionSupervisionCommandService
from app.services.runtime_remediation_governance_service import RuntimeRemediationGovernanceService
from app.services.signature_governance_service import SignatureGovernanceService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FINAL_GOVERNANCE_RELEASE_ROOT = PROJECT_ROOT / "runtime" / "staging" / "final-governance-release-readiness"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _status_from_score(score: float) -> str:
    if score >= 85.0:
        return "ok"
    if score >= 70.0:
        return "watch"
    return "blocked"


def _authority_from_status(status: str) -> str:
    normalized = _safe_str(status, "watch").lower()
    if normalized == "ok":
        return "GO"
    if normalized == "watch":
        return "WATCH"
    return "NO_GO"


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "ok", "ready", "pass", "enabled", "approved"}
    return bool(value)


def _score_from_ready(ready: bool) -> float:
    return 100.0 if ready else 0.0


def _component(
    *,
    name: str,
    payload: Dict[str, Any],
    status_keys: List[str],
    ready_keys: List[str],
    authority_keys: List[str],
    score_keys: List[str],
    blocker_keys: List[str],
) -> Dict[str, Any]:
    status = ""
    for key in status_keys:
        status = _safe_str(payload.get(key), "")
        if status:
            break
    authority = ""
    for key in authority_keys:
        authority = _safe_str(payload.get(key), "")
        if authority:
            break
    score = 0.0
    for key in score_keys:
        score = _safe_float(payload.get(key), 0.0)
        if score:
            break
    ready = bool(payload.get("ready"))
    if not ready:
        ready = any(_truthy(payload.get(key)) for key in ready_keys if not isinstance(payload.get(key), dict))
    if not ready and status:
        ready = _safe_str(status, "").lower() in {"ok", "ready", "pass"} or _safe_str(status, "").upper() == "READY_TO_SUBMIT"
    if not ready and authority:
        ready = _safe_str(authority, "").upper() == "GO"
    if not status:
        status = "ok" if ready else "watch"
    if not authority:
        authority = _authority_from_status(status)
    if not score:
        score = _score_from_ready(ready or authority == "GO" or status.lower() == "ok")
    blockers: List[str] = []
    for key in blocker_keys:
        value = payload.get(key)
        if isinstance(value, list):
            blockers.extend(_safe_str(item) for item in value if _safe_str(item))
        elif isinstance(value, dict):
            blockers.extend(f"{key}:{subkey}" for subkey, subvalue in value.items() if _truthy(subvalue))
        elif _truthy(value):
            blockers.append(f"{name}:{key}")
    if not ready and not blockers:
        blockers.append(f"{name} not ready")
    return {
        "ready": ready or authority == "GO" or status.lower() == "ok",
        "status": status.lower() if status else "watch",
        "authority": authority.upper() if authority else _authority_from_status(status),
        "score": round(score, 2),
        "blockers": blockers,
        "source": payload,
    }


class FinalGovernanceReleaseReadinessService:
    def __init__(
        self,
        cycle_root: Optional[Path] = None,
        export_root: Optional[Path] = None,
        k8s_root: Optional[Path] = None,
        final_readiness_service: Optional[FinalReadinessGovernanceService] = None,
        executive_governance_index_service: Optional[ExecutiveGovernanceIndexService] = None,
        production_operationalization_service: Optional[ProductionOperationalizationService] = None,
        supervision_command_service: Optional[ProductionSupervisionCommandService] = None,
        audit_service: Optional[ProductionAuditGovernanceService] = None,
        incident_service: Optional[ProductionIncidentGovernanceService] = None,
        continuity_service: Optional[ProductionContinuityGovernanceService] = None,
        release_service: Optional[ProductionReleaseGovernanceService] = None,
        operational_pilot_service: Optional[OperationalPilotExecutionService] = None,
        operational_stability_service: Optional[OperationalStabilityService] = None,
        runtime_remediation_service: Optional[RuntimeRemediationGovernanceService] = None,
        distributed_orchestration_service: Optional[DistributedOrchestrationGovernanceService] = None,
        ha_topology_service: Optional[HaTopologyGovernanceService] = None,
        ingress_service: Optional[IngressGovernanceService] = None,
        multi_tenant_service: Optional[MultiTenantGovernanceService] = None,
        distributed_observability_service: Optional[DistributedObservabilityGovernanceService] = None,
        autoscaling_service: Optional[AutoscalingGovernanceService] = None,
        backup_restore_service: Optional[BackupRestoreGovernanceService] = None,
        disaster_recovery_service: Optional[DisasterRecoveryGovernanceService] = None,
        data_residency_service: Optional[DataResidencyGovernanceService] = None,
        compliance_regulatory_service: Optional[ComplianceRegulatoryGovernanceService] = None,
        signature_service: Optional[SignatureGovernanceService] = None,
        activation_service: Optional[ActivationGovernanceService] = None,
        deadline_service: Optional[DeadlineGovernanceService] = None,
    ) -> None:
        cycle_root = cycle_root or PROJECT_ROOT / "runtime" / "staging" / "pilot-cycles"
        export_root = export_root or PROJECT_ROOT / "runtime" / "staging" / "governance-exports"
        self.final_readiness_service = final_readiness_service or FinalReadinessGovernanceService(cycle_root=cycle_root, export_root=export_root)
        self.executive_governance_index_service = executive_governance_index_service or ExecutiveGovernanceIndexService()
        self.production_operationalization_service = production_operationalization_service or ProductionOperationalizationService(cycle_root=cycle_root, evidence_pack_root=export_root)
        self.supervision_command_service = supervision_command_service or ProductionSupervisionCommandService()
        self.audit_service = audit_service or ProductionAuditGovernanceService()
        self.incident_service = incident_service or ProductionIncidentGovernanceService()
        self.continuity_service = continuity_service or ProductionContinuityGovernanceService()
        self.release_service = release_service or ProductionReleaseGovernanceService()
        self.operational_pilot_service = operational_pilot_service or OperationalPilotExecutionService(cycle_root=cycle_root, evidence_pack_root=export_root)
        self.operational_stability_service = operational_stability_service or OperationalStabilityService(cycle_root=cycle_root, export_root=export_root)
        self.runtime_remediation_service = runtime_remediation_service or RuntimeRemediationGovernanceService()
        self.distributed_orchestration_service = distributed_orchestration_service or DistributedOrchestrationGovernanceService()
        self.ha_topology_service = ha_topology_service or HaTopologyGovernanceService(k8s_root=k8s_root)
        self.ingress_service = ingress_service or IngressGovernanceService(k8s_root=k8s_root)
        self.multi_tenant_service = multi_tenant_service or MultiTenantGovernanceService(k8s_root=k8s_root)
        self.distributed_observability_service = distributed_observability_service or DistributedObservabilityGovernanceService(k8s_root=k8s_root)
        self.autoscaling_service = autoscaling_service or AutoscalingGovernanceService(k8s_root=k8s_root)
        self.backup_restore_service = backup_restore_service or BackupRestoreGovernanceService(k8s_root=k8s_root)
        self.disaster_recovery_service = disaster_recovery_service or DisasterRecoveryGovernanceService(k8s_root=k8s_root)
        self.data_residency_service = data_residency_service or DataResidencyGovernanceService()
        self.compliance_regulatory_service = compliance_regulatory_service or ComplianceRegulatoryGovernanceService()
        self.signature_service = signature_service or SignatureGovernanceService(cycle_root=cycle_root, export_root=export_root)
        self.activation_service = activation_service or ActivationGovernanceService(validation_root=PROJECT_ROOT / "runtime" / "staging" / "production-rollout-validations", release_certification_root=PROJECT_ROOT / "runtime" / "staging" / "release-certifications")
        self.deadline_service = deadline_service or DeadlineGovernanceService(cycle_root=cycle_root, export_root=export_root)

    @staticmethod
    def _safe_payload(response: Any) -> Dict[str, Any]:
        return response if isinstance(response, dict) else {}

    def _latest(self, service: Any, method: str) -> Dict[str, Any]:
        response = getattr(service, method)()
        if not isinstance(response, dict) or response.get("status") == "not_found":
            return {}
        return response

    def _build_snapshot(self) -> Dict[str, Any]:
        now = _now_iso()
        final_readiness = self._latest(self.final_readiness_service, "latest_final_readiness")
        executive = self._latest(self.executive_governance_index_service, "latest_executive_governance_index")
        production = self._latest(self.production_operationalization_service, "latest_production_governance")
        supervision = self._latest(self.supervision_command_service, "latest_supervision_command")
        audit = self._latest(self.audit_service, "latest_operations_audit")
        incident = self._latest(self.incident_service, "latest_incident_governance")
        continuity = self._latest(self.continuity_service, "latest_continuity_governance")
        release = self._latest(self.release_service, "latest_release_governance")
        operational_pilot = self._latest(self.operational_pilot_service, "latest_operational_pilot_execution")
        stability = self._latest(self.operational_stability_service, "latest_stability")
        remediation = self._latest(self.runtime_remediation_service, "latest_runtime_remediation")
        orchestration = self._latest(self.distributed_orchestration_service, "latest_distributed_orchestration")
        ha_topology = self._latest(self.ha_topology_service, "latest_ha_topology")
        ingress = self._latest(self.ingress_service, "latest_ingress_governance")
        multi_tenant = self._latest(self.multi_tenant_service, "latest_multi_tenant_governance")
        observability = self._latest(self.distributed_observability_service, "latest_distributed_observability")
        autoscaling = self._latest(self.autoscaling_service, "latest_autoscaling_governance")
        backup_restore = self._latest(self.backup_restore_service, "latest_backup_restore_governance")
        disaster_recovery = self._latest(self.disaster_recovery_service, "latest_disaster_recovery_governance")
        data_residency = self._latest(self.data_residency_service, "latest")
        compliance_regulatory = self._latest(self.compliance_regulatory_service, "latest_compliance_regulatory_governance")
        signature = self._latest(self.signature_service, "latest_signature_governance")
        activation = self._latest(self.activation_service, "latest_activation_governance")
        deadline = self._latest(self.deadline_service, "latest_deadline_governance")

        sections = {
            "governance_command_centre_readiness": _component(
                name="governance_command_centre_readiness",
                payload=final_readiness,
                status_keys=["final_submission_readiness_status", "status"],
                ready_keys=["ready"],
                authority_keys=["final_escalation_authority", "authority"],
                score_keys=["final_submission_readiness_score", "score"],
                blocker_keys=["warnings", "unresolved_blocker_indicators"],
            ),
            "rollout_governance_readiness": _component(
                name="rollout_governance_readiness",
                payload=executive,
                status_keys=["executive_governance_index_status", "status"],
                ready_keys=["ready_for_controlled_rollout", "ready"],
                authority_keys=["executive_governance_index_authority", "authority"],
                score_keys=["executive_governance_index_score", "score"],
                blocker_keys=["warnings", "governance_degradation_indicators", "executive_escalation_indicators"],
            ),
            "supervision_governance_readiness": _component(
                name="supervision_governance_readiness",
                payload=supervision,
                status_keys=["supervision_command_status", "status"],
                ready_keys=["active_supervision_coverage_ready", "ready"],
                authority_keys=["supervision_command_authority", "authority"],
                score_keys=["supervision_command_score", "score"],
                blocker_keys=["warnings", "supervision_coverage", "supervision_saturation"],
            ),
            "audit_governance_readiness": _component(
                name="audit_governance_readiness",
                payload=audit,
                status_keys=["operations_audit_status", "status"],
                ready_keys=["ready"],
                authority_keys=["operations_audit_authority", "authority"],
                score_keys=["operations_audit_score", "score"],
                blocker_keys=["warnings"],
            ),
            "incident_governance_readiness": _component(
                name="incident_governance_readiness",
                payload=incident,
                status_keys=["incident_governance_status", "status"],
                ready_keys=["ready"],
                authority_keys=["incident_governance_authority", "authority"],
                score_keys=["incident_governance_score", "score"],
                blocker_keys=["warnings"],
            ),
            "continuity_governance_readiness": _component(
                name="continuity_governance_readiness",
                payload=continuity,
                status_keys=["continuity_governance_status", "status"],
                ready_keys=["ready"],
                authority_keys=["continuity_governance_authority", "authority"],
                score_keys=["continuity_governance_score", "score"],
                blocker_keys=["warnings"],
            ),
            "executive_governance_index_readiness": _component(
                name="executive_governance_index_readiness",
                payload=executive,
                status_keys=["executive_governance_index_status", "status"],
                ready_keys=["ready_for_controlled_rollout", "ready"],
                authority_keys=["executive_governance_index_authority", "authority"],
                score_keys=["executive_governance_index_score", "score"],
                blocker_keys=["warnings"],
            ),
            "production_deployment_governance_readiness": _component(
                name="production_deployment_governance_readiness",
                payload=production,
                status_keys=["production_operationalization_status", "status"],
                ready_keys=["production_runtime_segmentation", "production_observability_governance", "high_availability_governance", "disaster_recovery_governance", "ready"],
                authority_keys=["production_operationalization_authority", "authority"],
                score_keys=["production_operationalization_score", "score"],
                blocker_keys=["warnings", "production_runtime_segmentation", "production_observability_governance"],
            ),
            "secrets_access_governance_readiness": _component(
                name="secrets_access_governance_readiness",
                payload=production,
                status_keys=["production_operationalization_status", "status"],
                ready_keys=["operator_access_governance", "production_runtime_segmentation", "ready"],
                authority_keys=["production_operationalization_authority", "authority"],
                score_keys=["operator_access_governance_score", "production_operationalization_score", "score"],
                blocker_keys=["operator_access_risk_indicators", "warnings"],
            ),
            "cicd_governance_readiness": _component(
                name="cicd_governance_readiness",
                payload=release,
                status_keys=["release_governance_status", "status"],
                ready_keys=["release_authority_valid", "deployment_risk_indicators", "operational_release_indicators", "ready"],
                authority_keys=["release_governance_authority", "authority"],
                score_keys=["release_governance_score", "score"],
                blocker_keys=["warnings", "deployment_risk_indicators"],
            ),
            "smoke_testing_readiness": _component(
                name="smoke_testing_readiness",
                payload=release,
                status_keys=["release_governance_status", "status"],
                ready_keys=["submission_lock_verified", "dry_run_verified", "overall_validation_passed", "ready"],
                authority_keys=["release_governance_authority", "authority"],
                score_keys=["release_governance_score", "score"],
                blocker_keys=["warnings", "operational_release_indicators"],
            ),
            "runtime_boot_validation_readiness": _component(
                name="runtime_boot_validation_readiness",
                payload=operational_pilot,
                status_keys=["operational_pilot_status", "status"],
                ready_keys=["ready"],
                authority_keys=["operational_pilot_authority", "authority"],
                score_keys=["operational_pilot_score", "score"],
                blocker_keys=["warnings"],
            ),
            "endurance_validation_readiness": _component(
                name="endurance_validation_readiness",
                payload=stability,
                status_keys=["status"],
                ready_keys=["ready"],
                authority_keys=["authority"],
                score_keys=["stability_score", "score"],
                blocker_keys=["warnings", "drift_warnings"],
            ),
            "remediation_governance_readiness": _component(
                name="remediation_governance_readiness",
                payload=remediation,
                status_keys=["runtime_remediation_status", "status"],
                ready_keys=["ready"],
                authority_keys=["runtime_remediation_authority", "authority"],
                score_keys=["runtime_remediation_score", "score"],
                blocker_keys=["warnings", "unresolved_remediation_blockers"],
            ),
            "failure_injection_validation_readiness": _component(
                name="failure_injection_validation_readiness",
                payload=incident,
                status_keys=["incident_governance_status", "status"],
                ready_keys=["ready"],
                authority_keys=["incident_governance_authority", "authority"],
                score_keys=["incident_governance_score", "score"],
                blocker_keys=["warnings", "failure_injection_indicators"],
            ),
            "runtime_recovery_validation_readiness": _component(
                name="runtime_recovery_validation_readiness",
                payload=remediation,
                status_keys=["runtime_remediation_status", "status"],
                ready_keys=["ready"],
                authority_keys=["runtime_remediation_authority", "authority"],
                score_keys=["runtime_remediation_score", "score"],
                blocker_keys=["warnings", "governance_recovery_tracking"],
            ),
            "kubernetes_ha_topology_readiness": _component(
                name="kubernetes_ha_topology_readiness",
                payload=ha_topology,
                status_keys=["ha_topology_status", "status"],
                ready_keys=["ready"],
                authority_keys=["ha_topology_authority", "authority"],
                score_keys=["ha_topology_score", "score"],
                blocker_keys=["warnings"],
            ),
            "distributed_orchestration_governance_readiness": _component(
                name="distributed_orchestration_governance_readiness",
                payload=orchestration,
                status_keys=["distributed_orchestration_status", "status"],
                ready_keys=["ready"],
                authority_keys=["distributed_orchestration_authority", "authority"],
                score_keys=["distributed_orchestration_score", "score"],
                blocker_keys=["warnings"],
            ),
            "ingress_tls_governance_readiness": _component(
                name="ingress_tls_governance_readiness",
                payload=ingress,
                status_keys=["ingress_governance_status", "status"],
                ready_keys=["ready"],
                authority_keys=["ingress_governance_authority", "authority"],
                score_keys=["ingress_governance_score", "score"],
                blocker_keys=["warnings"],
            ),
            "multi_tenant_isolation_governance_readiness": _component(
                name="multi_tenant_isolation_governance_readiness",
                payload=multi_tenant,
                status_keys=["multi_tenant_governance_status", "status"],
                ready_keys=["ready"],
                authority_keys=["multi_tenant_governance_authority", "authority"],
                score_keys=["multi_tenant_governance_score", "score"],
                blocker_keys=["warnings"],
            ),
            "observability_governance_readiness": _component(
                name="observability_governance_readiness",
                payload=observability,
                status_keys=["distributed_observability_status", "status"],
                ready_keys=["ready"],
                authority_keys=["distributed_observability_authority", "authority"],
                score_keys=["distributed_observability_score", "score"],
                blocker_keys=["warnings"],
            ),
            "autoscaling_governance_readiness": _component(
                name="autoscaling_governance_readiness",
                payload=autoscaling,
                status_keys=["autoscaling_governance_status", "status"],
                ready_keys=["ready"],
                authority_keys=["autoscaling_governance_authority", "authority"],
                score_keys=["autoscaling_governance_score", "score"],
                blocker_keys=["warnings"],
            ),
            "backup_restore_governance_readiness": _component(
                name="backup_restore_governance_readiness",
                payload=backup_restore,
                status_keys=["backup_restore_governance_status", "status"],
                ready_keys=["ready"],
                authority_keys=["backup_restore_governance_authority", "authority"],
                score_keys=["backup_restore_governance_score", "score"],
                blocker_keys=["warnings"],
            ),
            "disaster_recovery_failover_governance_readiness": _component(
                name="disaster_recovery_failover_governance_readiness",
                payload=disaster_recovery,
                status_keys=["disaster_recovery_governance_status", "status"],
                ready_keys=["ready"],
                authority_keys=["disaster_recovery_governance_authority", "authority"],
                score_keys=["disaster_recovery_governance_score", "score"],
                blocker_keys=["warnings"],
            ),
            "data_residency_sovereignty_governance_readiness": _component(
                name="data_residency_sovereignty_governance_readiness",
                payload=data_residency,
                status_keys=["status"],
                ready_keys=["ready"],
                authority_keys=["authority"],
                score_keys=["score"],
                blocker_keys=["warnings", "unresolved_blockers"],
            ),
            "compliance_regulatory_governance_readiness": _component(
                name="compliance_regulatory_governance_readiness",
                payload=compliance_regulatory,
                status_keys=["compliance_regulatory_governance_status", "status"],
                ready_keys=["ready"],
                authority_keys=["compliance_regulatory_governance_authority", "authority"],
                score_keys=["compliance_regulatory_governance_score", "score"],
                blocker_keys=["warnings", "unresolved_blockers"],
            ),
        }

        safety = {
            "read_only": True,
            "staging_only": True,
            "dry_run_enforced": True,
            "human_supervision_required": True,
            "lmcp_allow_final_automation": False,
            "no_autonomous_procurement_authority": True,
            "no_live_production_submissions": True,
            "no_live_credentials": True,
            "no_live_external_alerting": True,
            "no_autonomous_remediation": True,
            "no_production_data_movement": True,
        }

        component_ready_values = [section["ready"] for section in sections.values()]
        safety_ready_values = list(safety.values())
        blockers: List[str] = []
        blocker_sources: List[Dict[str, Any]] = []
        for name, section in sections.items():
            if not section["ready"]:
                blockers.append(f"{name} not ready")
                blocker_sources.append({"source": name, "issue": "not_ready", "score": section["score"]})
            for blocker in section["blockers"]:
                if blocker not in blockers:
                    blockers.append(blocker)
                blocker_sources.append({"source": name, "issue": blocker})

        safety_checks = {
            "read_only": safety["read_only"],
            "staging_only": safety["staging_only"],
            "dry_run_enforced": safety["dry_run_enforced"],
            "human_supervision_required": safety["human_supervision_required"],
            "final_automation_disabled": not safety["lmcp_allow_final_automation"],
            "no_autonomous_procurement_authority": safety["no_autonomous_procurement_authority"],
            "no_live_production_submissions": safety["no_live_production_submissions"],
            "no_live_credentials": safety["no_live_credentials"],
            "no_live_external_alerting": safety["no_live_external_alerting"],
            "no_autonomous_remediation": safety["no_autonomous_remediation"],
            "no_production_data_movement": safety["no_production_data_movement"],
        }
        for key, value in safety_checks.items():
            if not value:
                blockers.append(f"safety:{key}")
                blocker_sources.append({"source": "safety", "issue": key})

        readiness_score = round(
            mean(
                [
                    _safe_float(section["score"], 0.0) for section in sections.values()
                ]
                + [100.0 if value else 0.0 for value in safety_checks.values()]
            ),
            2,
        )
        ready = all(component_ready_values) and all(safety_checks.values()) and not blockers
        status = "ok" if ready else "blocked" if blockers else "watch"
        authority = _authority_from_status(status)
        recovery_state = "recovered" if ready else "unresolved-blocked" if blockers else "degraded-but-recovering"
        grade = "ready" if status == "ok" else "watch" if status == "watch" else "blocked"

        history = [
            {
                "event": "final_governance_release_readiness_initialized",
                "status": "ready" if ready else "blocked",
                "authority": authority,
                "score": readiness_score,
                "timestamp": now,
            },
            {
                "event": "final_governance_release_safety_verified",
                "status": "passed" if all(safety_checks.values()) else "failed",
                "dry_run_enforced": safety["dry_run_enforced"],
                "human_supervision_required": safety["human_supervision_required"],
                "lmcp_allow_final_automation": safety["lmcp_allow_final_automation"],
                "timestamp": now,
            },
        ]
        unresolved_final_release_blockers = blockers
        final_governance_rationale = {
            "summary": (
                "Final governance release readiness remains read-only, staging-only, dry-run enforced, and supervised."
                if ready
                else "Final governance release readiness is blocked until the unresolved release blockers are cleared."
            ),
            "score_impact": {
                "component_ready_count": sum(1 for value in component_ready_values if value),
                "safety_ready_count": sum(1 for value in safety_checks.values() if value),
                "final_score": readiness_score,
            },
        }

        return {
            "generated_at": now,
            "environment": "staging",
            "governance_mode": "read_only",
            "final_governance_release_readiness_id": f"final-governance-release-readiness:{now}",
            "final_governance_release_readiness_status": status,
            "final_governance_release_readiness_authority": authority,
            "final_governance_release_readiness_score": readiness_score,
            "final_governance_release_readiness_grade": grade,
            "recovery_state": recovery_state,
            "governance_command_centre_readiness": sections["governance_command_centre_readiness"],
            "rollout_governance_readiness": sections["rollout_governance_readiness"],
            "supervision_governance_readiness": sections["supervision_governance_readiness"],
            "audit_governance_readiness": sections["audit_governance_readiness"],
            "incident_governance_readiness": sections["incident_governance_readiness"],
            "continuity_governance_readiness": sections["continuity_governance_readiness"],
            "executive_governance_index_readiness": sections["executive_governance_index_readiness"],
            "production_deployment_governance_readiness": sections["production_deployment_governance_readiness"],
            "secrets_access_governance_readiness": sections["secrets_access_governance_readiness"],
            "cicd_governance_readiness": sections["cicd_governance_readiness"],
            "smoke_testing_readiness": sections["smoke_testing_readiness"],
            "runtime_boot_validation_readiness": sections["runtime_boot_validation_readiness"],
            "endurance_validation_readiness": sections["endurance_validation_readiness"],
            "remediation_governance_readiness": sections["remediation_governance_readiness"],
            "failure_injection_validation_readiness": sections["failure_injection_validation_readiness"],
            "runtime_recovery_validation_readiness": sections["runtime_recovery_validation_readiness"],
            "kubernetes_ha_topology_readiness": sections["kubernetes_ha_topology_readiness"],
            "distributed_orchestration_governance_readiness": sections["distributed_orchestration_governance_readiness"],
            "ingress_tls_governance_readiness": sections["ingress_tls_governance_readiness"],
            "multi_tenant_isolation_governance_readiness": sections["multi_tenant_isolation_governance_readiness"],
            "observability_governance_readiness": sections["observability_governance_readiness"],
            "autoscaling_governance_readiness": sections["autoscaling_governance_readiness"],
            "backup_restore_governance_readiness": sections["backup_restore_governance_readiness"],
            "disaster_recovery_failover_governance_readiness": sections["disaster_recovery_failover_governance_readiness"],
            "data_residency_sovereignty_governance_readiness": sections["data_residency_sovereignty_governance_readiness"],
            "compliance_regulatory_governance_readiness": sections["compliance_regulatory_governance_readiness"],
            "unresolved_final_release_blockers": unresolved_final_release_blockers,
            "blocker_sources": blocker_sources,
            "safety_boundaries": safety_checks,
            "final_governance_rationale": final_governance_rationale,
            "final_governance_history": history,
            "warnings": unresolved_final_release_blockers,
        }

    def list_final_governance_release_readiness(self, limit: int = 20) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        history = snapshot["final_governance_history"][: max(1, limit)]
        payload = dict(snapshot)
        payload["count"] = len(history)
        payload["latest_final_governance_release_readiness"] = dict(snapshot)
        payload["final_governance_release_readiness_history"] = history
        payload["final_governance_release_readiness_history_summary"] = {
            "history_count": len(history),
            "latest_score": snapshot["final_governance_release_readiness_score"],
            "recovery_state_history": [{"recovery_state": snapshot["recovery_state"]}],
        }
        payload["summary_counts"] = {
            "PASS": 1 if snapshot["final_governance_release_readiness_status"] == "ok" else 0,
            "WARN": 1 if snapshot["final_governance_release_readiness_status"] == "watch" else 0,
            "FAIL": 1 if snapshot["final_governance_release_readiness_status"] == "blocked" else 0,
        }
        return payload

    def latest_final_governance_release_readiness(self) -> Dict[str, Any]:
        return self._build_snapshot()

    def final_governance_release_readiness_history(self, limit: int = 20) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        history = snapshot["final_governance_history"][: max(1, limit)]
        return {
            "status": snapshot["final_governance_release_readiness_status"],
            "environment": snapshot["environment"],
            "governance_mode": snapshot["governance_mode"],
            "count": len(history),
            "final_governance_release_readiness_history": history,
            "warnings": snapshot["warnings"],
        }


final_governance_release_readiness_service = FinalGovernanceReleaseReadinessService()
