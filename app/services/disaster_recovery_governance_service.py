from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional
import re

from app.services.backup_restore_governance_service import BackupRestoreGovernanceService
from app.services.multi_tenant_governance_service import MultiTenantGovernanceService
from app.services.operational_exception_service import _safe_dict, _safe_float, _safe_int, _safe_list, _safe_str
from app.services.production_continuity_governance_service import ProductionContinuityGovernanceService
from app.services.production_supervision_command_service import ProductionSupervisionCommandService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
K8S_ROOT = PROJECT_ROOT / "k8s"
BASE_DIR = K8S_ROOT / "base"
STAGING_DIR = K8S_ROOT / "overlays" / "staging"
PRODUCTION_DIR = K8S_ROOT / "overlays" / "production"
DR_REPORT_FILE = PROJECT_ROOT / "docs" / "DISASTER_RECOVERY_FAILOVER_GOVERNANCE_REPORT.md"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "ok", "ready", "enabled", "placeholder", "pass"}
    return bool(value)


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


def _history_points(values: List[float]) -> Dict[str, Any]:
    if not values:
        return {"trend": "unknown", "delta": 0.0, "average": 0.0, "latest": 0.0, "previous": 0.0, "points": []}
    latest = values[0]
    previous = values[1] if len(values) > 1 else latest
    delta = round(latest - previous, 2)
    if delta > 2.0:
        trend = "improving"
    elif delta < -2.0:
        trend = "declining"
    else:
        trend = "stable"
    return {
        "trend": trend,
        "delta": delta,
        "average": round(mean(values), 2),
        "latest": latest,
        "previous": previous,
        "points": values,
    }


def _dedupe(values: List[str]) -> List[str]:
    unique: List[str] = []
    for value in values:
        text = _safe_str(value)
        if text and text not in unique:
            unique.append(text)
    return unique


def _component(ready: bool, evidence: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "ready": ready,
        "status": "PASS" if ready else "WARN",
        "score": 100.0 if ready else 0.0,
        "evidence": evidence or {},
    }


def _contains_all(text: str, needles: List[str]) -> bool:
    return all(needle in text for needle in needles)


def _extract_int(text: str, pattern: str) -> int:
    match = re.search(pattern, text)
    return int(match.group(1)) if match else 0


def _records_all_pass(records: List[Any]) -> bool:
    if not records:
        return False
    for record in records:
        if isinstance(record, dict):
            status = _safe_str(record.get("status"), "").upper()
            if status and status != "PASS":
                return False
            if "ready" in record and not _truthy(record.get("ready")):
                return False
            if "status" not in record and "ready" not in record and not any(_truthy(value) for value in record.values()):
                return False
        elif not _truthy(record):
            return False
    return True


class DisasterRecoveryGovernanceService:
    def __init__(
        self,
        k8s_root: Optional[Path] = None,
        backup_restore_governance_service: Optional[BackupRestoreGovernanceService] = None,
        continuity_governance_service: Optional[ProductionContinuityGovernanceService] = None,
        multi_tenant_governance_service: Optional[MultiTenantGovernanceService] = None,
        supervision_command_service: Optional[ProductionSupervisionCommandService] = None,
    ) -> None:
        self.k8s_root = k8s_root or K8S_ROOT
        self.base_dir = self.k8s_root / "base"
        self.staging_dir = self.k8s_root / "overlays" / "staging"
        self.production_dir = self.k8s_root / "overlays" / "production"
        self.backup_restore_governance_service = backup_restore_governance_service or BackupRestoreGovernanceService(k8s_root=self.k8s_root)
        self.continuity_governance_service = continuity_governance_service or ProductionContinuityGovernanceService()
        self.multi_tenant_governance_service = multi_tenant_governance_service or MultiTenantGovernanceService(k8s_root=self.k8s_root)
        self.supervision_command_service = supervision_command_service or ProductionSupervisionCommandService()

    def _manifest_paths(self) -> Dict[str, Path]:
        return {
            "kustomization": self.base_dir / "kustomization.yaml",
            "namespace": self.base_dir / "namespace.yaml",
            "configmap": self.base_dir / "configmap.yaml",
            "secret_placeholders": self.base_dir / "secret-placeholders.yaml",
            "regional_failover_placeholder": self.base_dir / "regional-failover-placeholder.yaml",
            "warm_standby_placeholder": self.base_dir / "warm-standby-placeholder.yaml",
            "dns_failover_placeholder": self.base_dir / "dns-failover-placeholder.yaml",
            "cross_region_backup_placeholder": self.base_dir / "cross-region-backup-placeholder.yaml",
            "dr_rehearsal_job_placeholder": self.base_dir / "dr-rehearsal-job-placeholder.yaml",
            "staging_kustomization": self.staging_dir / "kustomization.yaml",
            "production_kustomization": self.production_dir / "kustomization.yaml",
            "staging_patch": self.staging_dir / "patches" / "staging-safety-patch.yaml",
            "production_patch": self.production_dir / "patches" / "production-safety-patch.yaml",
        }

    @staticmethod
    def _text(path: Path) -> str:
        return path.read_text(encoding="utf-8") if path.exists() else ""

    @staticmethod
    def _file_ready(path: Path) -> bool:
        return path.exists() and path.is_file()

    def _safety_model(self) -> Dict[str, Any]:
        production_text = self._text(self.production_dir / "patches" / "production-safety-patch.yaml")
        staging_text = self._text(self.staging_dir / "patches" / "staging-safety-patch.yaml")
        all_text = "\n".join(
            self._text(path)
            for path in self.k8s_root.rglob("*")
            if path.is_file() and path.suffix.lower() in {".yaml", ".yml", ".md"}
        )
        cloud_markers = ["BEGIN PRIVATE KEY", "AKIA", "ghp_", "sk-", "xoxb-", "real-password", "prod-password", "password123"]
        dns_markers = ["dns_api_key", "dns_secret", "dns_password", "cloudflare_api_token", "route53_secret", "real-dns"]
        return {
            "final_automation_disabled": 'LMCP_ALLOW_FINAL_AUTOMATION: "false"' in production_text,
            "dry_run_mode_enabled": 'LMCP_DRY_RUN_MODE: "true"' in production_text,
            "human_supervision_required": 'LMCP_REQUIRE_HUMAN_SUPERVISION: "true"' in production_text,
            "submission_lock_required": "LMCP_SUBMISSION_LOCK_FILE:" in production_text,
            "production_overlay_separated_from_staging": "LMCP_ENV: staging" in staging_text and "LMCP_ENV: production" in production_text,
            "embedded_cloud_credentials_found": any(marker in all_text for marker in cloud_markers),
            "live_dns_credentials_found": any(marker in all_text.lower() for marker in dns_markers),
            "autonomous_production_authority_introduced": 'LMCP_ALLOW_FINAL_AUTOMATION: "true"' in all_text,
        }

    def _regional_failover_readiness(self) -> Dict[str, Any]:
        text = self._text(self.base_dir / "regional-failover-placeholder.yaml")
        rpo_minutes = _extract_int(text, r'rpo_minutes:\s*"?(\d+)"?')
        rto_minutes = _extract_int(text, r'rto_minutes:\s*"?(\d+)"?')
        ready = _contains_all(
            text,
            [
                "regional-failover-placeholder",
                "kind: ConfigMap",
                "regional_failover",
                "failover_region",
                "rpo_minutes",
                "rto_minutes",
            ],
        )
        return {
            "ready": ready,
            "primary_region": "placeholder" if "primary_region" in text else "",
            "failover_region": "placeholder" if "failover_region" in text else "",
            "rpo_minutes": rpo_minutes,
            "rto_minutes": rto_minutes,
        }

    def _warm_standby_readiness(self) -> Dict[str, Any]:
        text = self._text(self.base_dir / "warm-standby-placeholder.yaml")
        ready = _contains_all(
            text,
            [
                "warm-standby-placeholder",
                "kind: Deployment",
                "standby_mode",
                "standby_region",
                "replicas:",
            ],
        ) and _extract_int(text, r"replicas:\s*(\d+)") >= 1
        return {
            "ready": ready,
            "replicas": _extract_int(text, r"replicas:\s*(\d+)"),
            "standby_region": "placeholder" if "standby_region" in text else "",
            "standby_mode": "placeholder" if "standby_mode" in text else "",
        }

    def _cross_region_backup_readiness(self) -> Dict[str, Any]:
        text = self._text(self.base_dir / "cross-region-backup-placeholder.yaml")
        rpo_minutes = _extract_int(text, r'rpo_minutes:\s*"?(\d+)"?')
        ready = _contains_all(
            text,
            [
                "cross-region-backup-placeholder",
                "kind: CronJob",
                "cross_region_backup",
                "backup_region",
                "rpo_minutes",
            ],
        )
        return {
            "ready": ready,
            "backup_region": "placeholder" if "backup_region" in text else "",
            "rpo_minutes": rpo_minutes,
            "backup_schedule": "placeholder" if "backup_schedule" in text else "",
        }

    def _dns_failover_readiness(self) -> Dict[str, Any]:
        text = self._text(self.base_dir / "dns-failover-placeholder.yaml")
        rto_minutes = _extract_int(text, r'rto_minutes:\s*"?(\d+)"?')
        ready = _contains_all(
            text,
            [
                "dns-failover-placeholder",
                "kind: ConfigMap",
                "dns_failover",
                "primary_dns_record",
                "failover_dns_record",
                "dns_provider",
            ],
        )
        return {
            "ready": ready,
            "primary_dns_record": "placeholder" if "primary_dns_record" in text else "",
            "failover_dns_record": "placeholder" if "failover_dns_record" in text else "",
            "dns_provider": "placeholder" if "dns_provider" in text else "",
            "rto_minutes": rto_minutes,
        }

    def _dr_rehearsal_readiness(self) -> Dict[str, Any]:
        text = self._text(self.base_dir / "dr-rehearsal-job-placeholder.yaml")
        rto_minutes = _extract_int(text, r'rto_minutes:\s*"?(\d+)"?')
        ready = _contains_all(
            text,
            [
                "dr-rehearsal-job-placeholder",
                "kind: Job",
                "dr_rehearsal",
                "failover_drill",
                "rto_minutes",
            ],
        )
        return {
            "ready": ready,
            "rto_minutes": rto_minutes,
            "failover_drill": "placeholder" if "failover_drill" in text else "",
        }

    def _dr_runbook_readiness(self) -> Dict[str, Any]:
        text = self._text(DR_REPORT_FILE)
        ready = _contains_all(
            text.lower(),
            [
                "disaster recovery",
                "runbook",
                "failover",
                "rpo",
                "rto",
            ],
        )
        return {
            "ready": ready,
            "report_present": DR_REPORT_FILE.exists(),
            "report_path": str(DR_REPORT_FILE),
        }

    def _backup_and_continuity_readiness(self) -> Dict[str, Any]:
        backup_restore = _safe_dict(self.backup_restore_governance_service.latest_backup_restore_governance())
        continuity = _safe_dict(self.continuity_governance_service.latest_continuity_governance())
        backup_rpo = _safe_dict(backup_restore.get("rpo_visibility"))
        backup_rto = _safe_dict(backup_restore.get("rto_visibility"))
        continuity_rehearsals = _safe_list(continuity.get("disaster_recovery_rehearsal_status"))
        continuity_escalation = _safe_list(continuity.get("recovery_escalation_readiness"))
        continuity_timing = _safe_list(continuity.get("recovery_timing_indicators"))
        continuity_ready = all(
            [
                _records_all_pass(continuity_rehearsals),
                _records_all_pass(continuity_escalation),
                _records_all_pass(continuity_timing),
            ]
        )
        return {
            "backup_restore": backup_restore,
            "continuity": continuity,
            "backup_rpo_ready": _truthy(backup_rpo.get("ready")),
            "backup_rto_ready": _truthy(backup_rto.get("ready")),
            "continuity_ready": continuity_ready,
        }

    def _tenant_recovery_boundaries(self) -> Dict[str, Any]:
        multi_tenant = _safe_dict(self.multi_tenant_governance_service.latest_multi_tenant_governance())
        safety_model = _safe_dict(multi_tenant.get("safety_model"))
        tenant_isolation = _safe_dict(multi_tenant.get("tenant_isolation_readiness"))
        namespace = _safe_dict(multi_tenant.get("namespace_segregation_readiness"))
        workload = _safe_dict(multi_tenant.get("tenant_workload_separation"))
        rbac = _safe_dict(multi_tenant.get("rbac_tenant_boundaries"))
        storage = _safe_dict(multi_tenant.get("storage_isolation_readiness"))
        ingress = _safe_dict(multi_tenant.get("ingress_tenancy_segregation"))
        supervision = _safe_dict(multi_tenant.get("supervision_tenancy_coverage"))
        leakage = _safe_dict(multi_tenant.get("cross_tenant_leakage_indicators"))
        ready = all(
            [
                _truthy(tenant_isolation.get("ready")),
                _truthy(namespace.get("ready")),
                _truthy(workload.get("ready")),
                _truthy(rbac.get("ready")),
                _truthy(storage.get("ready")),
                _truthy(ingress.get("ready")),
                _truthy(supervision.get("ready")),
                _truthy(leakage.get("cross_tenant_leakage_safe")),
                _truthy(safety_model.get("tenant_onboarding_disabled")),
            ]
        )
        return {
            "ready": ready,
            "tenant_isolation_ready": _truthy(tenant_isolation.get("ready")),
            "namespace_segregation_ready": _truthy(namespace.get("ready")),
            "tenant_workload_separation_ready": _truthy(workload.get("ready")),
            "rbac_tenant_boundaries_ready": _truthy(rbac.get("ready")),
            "storage_isolation_ready": _truthy(storage.get("ready")),
            "ingress_tenancy_segregation_ready": _truthy(ingress.get("ready")),
            "supervision_tenancy_coverage_ready": _truthy(supervision.get("ready")),
            "cross_tenant_leakage_safe": _truthy(leakage.get("cross_tenant_leakage_safe")),
            "tenant_onboarding_disabled": _truthy(safety_model.get("tenant_onboarding_disabled")),
            "safety_model": safety_model,
        }

    def _supervision_saturation(self) -> Dict[str, Any]:
        supervision_snapshot = _safe_dict(self.supervision_command_service.latest_supervision_command())
        workload = _safe_dict(supervision_snapshot.get("operational_workload_visibility"))
        saturation = _safe_dict(supervision_snapshot.get("supervision_saturation"))
        active_sessions = _safe_int(workload.get("active_session_count"), 0)
        workload_items = _safe_int(workload.get("workload_items"), _safe_int(workload.get("assigned_rfq_count"), 0) + _safe_int(workload.get("pending_approval_count"), 0))
        queue_backlog_count = _safe_int(saturation.get("queue_backlog_count"), 0)
        worker_backlog_count = _safe_int(saturation.get("worker_backlog_count"), 0)
        saturation_active = _truthy(saturation.get("supervision_saturation_active")) or active_sessions > 1 or workload_items > 2 or queue_backlog_count > 0 or worker_backlog_count > 0
        return {
            "supervision_saturation_active": saturation_active,
            "workload_pressure": _safe_str(workload.get("workload_pressure"), "low"),
            "active_session_count": active_sessions,
            "workload_items": workload_items,
            "queue_backlog_count": queue_backlog_count,
            "worker_backlog_count": worker_backlog_count,
        }

    def _snapshot(self) -> Dict[str, Any]:
        paths = self._manifest_paths()
        safety = self._safety_model()
        missing_files = [name for name, path in paths.items() if not self._file_ready(path)]

        regional_failover = self._regional_failover_readiness()
        warm_standby = self._warm_standby_readiness()
        cross_region_backup = self._cross_region_backup_readiness()
        dns_failover = self._dns_failover_readiness()
        dr_rehearsal = self._dr_rehearsal_readiness()
        dr_runbook = self._dr_runbook_readiness()
        backup_and_continuity = self._backup_and_continuity_readiness()
        tenant_boundaries = self._tenant_recovery_boundaries()
        saturation = self._supervision_saturation()

        backup_restore = _safe_dict(backup_and_continuity.get("backup_restore"))
        continuity = _safe_dict(backup_and_continuity.get("continuity"))
        backup_rpo = _safe_dict(backup_restore.get("rpo_visibility"))
        backup_rto = _safe_dict(backup_restore.get("rto_visibility"))
        continuity_escalation_ready = backup_and_continuity["continuity_ready"]
        backup_restore_ready = _truthy(backup_restore.get("backup_restore_governance_status") == "ok") or _truthy(backup_restore.get("recovery_state") == "recovered")

        rpo_rto_escalation_ready = all(
            [
                regional_failover["ready"],
                cross_region_backup["ready"],
                dr_rehearsal["ready"],
                backup_and_continuity["backup_rpo_ready"],
                backup_and_continuity["backup_rto_ready"],
                continuity_escalation_ready,
                dr_runbook["ready"],
                backup_restore_ready,
            ]
        )
        failover_orchestration_ready = all(
            [
                regional_failover["ready"],
                warm_standby["ready"],
                dns_failover["ready"],
                cross_region_backup["ready"],
                dr_rehearsal["ready"],
            ]
        )
        dr_governance_ready = all(
            [
                failover_orchestration_ready,
                dr_runbook["ready"],
                rpo_rto_escalation_ready,
                tenant_boundaries["ready"],
                safety["final_automation_disabled"],
                safety["dry_run_mode_enabled"],
                safety["human_supervision_required"],
                safety["submission_lock_required"],
                safety["production_overlay_separated_from_staging"],
                not safety["embedded_cloud_credentials_found"],
                not safety["live_dns_credentials_found"],
                not safety["autonomous_production_authority_introduced"],
            ]
        )

        failover_degradation_indicators = {
            "regional_failover_degradation": not regional_failover["ready"],
            "warm_standby_degradation": not warm_standby["ready"],
            "cross_region_backup_degradation": not cross_region_backup["ready"],
            "dns_failover_degradation": not dns_failover["ready"],
            "dr_rehearsal_degradation": not dr_rehearsal["ready"],
            "dr_runbook_degradation": not dr_runbook["ready"],
            "rpo_rto_escalation_degradation": not rpo_rto_escalation_ready,
            "tenant_recovery_boundary_degradation": not tenant_boundaries["ready"],
            "supervision_saturation_degradation": saturation["supervision_saturation_active"],
            "cloud_credentials_degradation": safety["embedded_cloud_credentials_found"],
            "dns_credentials_degradation": safety["live_dns_credentials_found"],
        }

        blocker_sources = [
            {
                "source": "regional_failover_placeholder",
                "ready": regional_failover["ready"],
                "blockers": [] if regional_failover["ready"] else ["regional failover placeholder is incomplete"],
            },
            {
                "source": "warm_standby_placeholder",
                "ready": warm_standby["ready"],
                "blockers": [] if warm_standby["ready"] else ["warm standby placeholder is incomplete"],
            },
            {
                "source": "cross_region_backup_placeholder",
                "ready": cross_region_backup["ready"],
                "blockers": [] if cross_region_backup["ready"] else ["cross-region backup placeholder is incomplete"],
            },
            {
                "source": "dns_failover_placeholder",
                "ready": dns_failover["ready"],
                "blockers": [] if dns_failover["ready"] else ["DNS failover placeholder is incomplete"],
            },
            {
                "source": "dr_rehearsal_job_placeholder",
                "ready": dr_rehearsal["ready"],
                "blockers": [] if dr_rehearsal["ready"] else ["DR rehearsal job placeholder is incomplete"],
            },
            {
                "source": "dr_runbook_report",
                "ready": dr_runbook["ready"],
                "blockers": [] if dr_runbook["ready"] else ["DR runbook report is incomplete"],
            },
            {
                "source": "rpo_rto_escalation_readiness",
                "ready": rpo_rto_escalation_ready,
                "blockers": [] if rpo_rto_escalation_ready else ["RPO/RTO escalation readiness is incomplete"],
            },
            {
                "source": "tenant_recovery_boundary_readiness",
                "ready": tenant_boundaries["ready"],
                "blockers": [] if tenant_boundaries["ready"] else ["tenant recovery boundaries are incomplete"],
            },
            {
                "source": "production_safety_controls",
                "ready": all(
                    [
                        safety["final_automation_disabled"],
                        safety["dry_run_mode_enabled"],
                        safety["human_supervision_required"],
                        safety["submission_lock_required"],
                        safety["production_overlay_separated_from_staging"],
                    ]
                ),
                "blockers": _dedupe(
                    ([] if safety["final_automation_disabled"] else ["final automation is not disabled"]) +
                    ([] if safety["dry_run_mode_enabled"] else ["dry-run mode is not enabled"]) +
                    ([] if safety["human_supervision_required"] else ["human supervision is not mandatory"]) +
                    ([] if safety["submission_lock_required"] else ["submission lock enforcement is missing"]) +
                    ([] if safety["production_overlay_separated_from_staging"] else ["production overlay is not separated from staging"]) +
                    ([] if not safety["embedded_cloud_credentials_found"] else ["live cloud credentials were detected"]) +
                    ([] if not safety["live_dns_credentials_found"] else ["live DNS credentials were detected"]) +
                    ([] if not safety["autonomous_production_authority_introduced"] else ["autonomous production authority was introduced"])
                ),
            },
            {
                "source": "supervision_saturation",
                "ready": not saturation["supervision_saturation_active"],
                "blockers": [] if not saturation["supervision_saturation_active"] else ["supervision saturation is active"],
            },
        ]

        unresolved_blockers = _dedupe([blocker for source in blocker_sources for blocker in _safe_list(source.get("blockers"))] + _safe_list(safety.get("warnings")))
        warnings = _dedupe(
            unresolved_blockers
            + (["supervision saturation remains visible"] if saturation["supervision_saturation_active"] else [])
            + (["DR runbook report is missing"] if not dr_runbook["ready"] else [])
        )

        component_scores = [
            100.0 if regional_failover["ready"] else 0.0,
            100.0 if warm_standby["ready"] else 0.0,
            100.0 if cross_region_backup["ready"] else 0.0,
            100.0 if dns_failover["ready"] else 0.0,
            100.0 if dr_rehearsal["ready"] else 0.0,
            100.0 if dr_runbook["ready"] else 0.0,
            100.0 if rpo_rto_escalation_ready else 0.0,
            100.0 if tenant_boundaries["ready"] else 0.0,
            100.0 if backup_and_continuity["backup_rpo_ready"] else 0.0,
            100.0 if backup_and_continuity["backup_rto_ready"] else 0.0,
            100.0 if continuity_escalation_ready else 0.0,
            100.0 if not saturation["supervision_saturation_active"] else 40.0,
            100.0 if all(not value for value in failover_degradation_indicators.values()) else 35.0,
        ]
        base_score = round(mean(component_scores), 2) if component_scores else 0.0
        deduction = (len(unresolved_blockers) * 5.0) + (len(warnings) * 1.5)
        score_after_deductions = max(0.0, round(base_score - deduction, 2))

        if unresolved_blockers:
            recovery_state = "unresolved-blocked"
            disaster_recovery_score = min(score_after_deductions, 69.99)
        elif warnings or saturation["supervision_saturation_active"] or not dr_governance_ready:
            recovery_state = "degraded-but-recovering"
            disaster_recovery_score = min(max(score_after_deductions, 70.0), 84.99)
        else:
            recovery_state = "recovered"
            disaster_recovery_score = max(score_after_deductions, 90.0)

        disaster_recovery_score = round(min(disaster_recovery_score, 100.0), 2)
        disaster_recovery_status = _status_from_score(disaster_recovery_score)
        if recovery_state == "unresolved-blocked":
            disaster_recovery_status = "blocked"
        elif recovery_state == "degraded-but-recovering":
            disaster_recovery_status = "watch"
        else:
            disaster_recovery_status = "ok"
        disaster_recovery_authority = _authority_from_status(disaster_recovery_status)
        disaster_recovery_grade = "ready" if recovery_state == "recovered" else "watch" if recovery_state == "degraded-but-recovering" else "blocked"
        recovery_state_history = [
            {
                "analysis_id": "disaster-recovery-governance:latest",
                "generated_at": _now_iso(),
                "recovery_state": recovery_state,
                "disaster_recovery_governance_score": disaster_recovery_score,
                "disaster_recovery_governance_status": disaster_recovery_status,
                "disaster_recovery_governance_authority": disaster_recovery_authority,
                "unresolved_blocker_count": len(unresolved_blockers),
            }
        ]
        recovery_rationale = {
            "state": recovery_state,
            "summary": (
                "Disaster recovery and regional failover controls are fully recovered."
                if recovery_state == "recovered"
                else "Disaster recovery controls are degraded but the staged topology is still converging."
                if recovery_state == "degraded-but-recovering"
                else "Disaster recovery blockers remain unresolved."
            ),
            "score_impact": {
                "base_score": round(base_score, 2),
                "deductions": round(deduction, 2),
                "final_score": disaster_recovery_score,
            },
            "state_basis": {
                "regional_failover_ready": regional_failover["ready"],
                "warm_standby_ready": warm_standby["ready"],
                "cross_region_backup_ready": cross_region_backup["ready"],
                "dns_failover_ready": dns_failover["ready"],
                "dr_runbook_ready": dr_runbook["ready"],
                "dr_rehearsal_ready": dr_rehearsal["ready"],
                "rpo_rto_escalation_ready": rpo_rto_escalation_ready,
                "tenant_recovery_boundary_ready": tenant_boundaries["ready"],
                "supervision_saturation_active": saturation["supervision_saturation_active"],
                "unresolved_blocker_count": len(unresolved_blockers),
            },
        }
        history_entry = {
            "analysis_id": "disaster-recovery-governance:latest",
            "generated_at": _now_iso(),
            "ready": disaster_recovery_status in {"ok", "watch"},
            "status": disaster_recovery_status,
            "score": disaster_recovery_score,
            "blockers": unresolved_blockers,
            "authority": disaster_recovery_authority,
            "disaster_recovery_governance_status": disaster_recovery_status,
            "disaster_recovery_governance_authority": disaster_recovery_authority,
            "disaster_recovery_governance_score": disaster_recovery_score,
            "disaster_recovery_governance_grade": disaster_recovery_grade,
            "recovery_state": recovery_state,
            "recovery_state_history": recovery_state_history,
            "unresolved_blockers": unresolved_blockers,
            "recovery_rationale": recovery_rationale,
            "blocker_sources": blocker_sources,
            "regional_failover_readiness": _component(regional_failover["ready"], regional_failover),
            "warm_standby_readiness": _component(warm_standby["ready"], warm_standby),
            "cross_region_backup_readiness": _component(cross_region_backup["ready"], cross_region_backup),
            "dns_failover_placeholder_readiness": _component(dns_failover["ready"], dns_failover),
            "dr_runbook_readiness": _component(dr_runbook["ready"], dr_runbook),
            "dr_rehearsal_readiness": _component(dr_rehearsal["ready"], dr_rehearsal),
            "rpo_rto_escalation_readiness": _component(rpo_rto_escalation_ready, {
                "backup_restore": backup_restore,
                "continuity": continuity,
                "rpo_visible": backup_and_continuity["backup_rpo_ready"],
                "rto_visible": backup_and_continuity["backup_rto_ready"],
            }),
            "tenant_recovery_boundary_readiness": _component(tenant_boundaries["ready"], tenant_boundaries),
            "failover_degradation_indicators": failover_degradation_indicators,
            "backup_restore_governance": backup_restore,
            "continuity_governance": continuity,
            "safety_model": safety,
            "warnings": warnings,
            "summary_counts": {
                "PASS": 1 if recovery_state == "recovered" else 0,
                "WARN": 1 if recovery_state == "degraded-but-recovering" else 0,
                "FAIL": 1 if recovery_state == "unresolved-blocked" else 0,
            },
        }
        return history_entry

    def _history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return [self._snapshot()][: max(1, int(limit))]

    def list_disaster_recovery_governance(self, limit: int = 20) -> Dict[str, Any]:
        latest = self._snapshot()
        history = self._history(limit=limit)
        scores = [float(item.get("disaster_recovery_governance_score", 0.0)) for item in history] or [latest["disaster_recovery_governance_score"]]
        summary = {
            "analysis_count": len(history),
            "latest_analysis_id": _safe_str(history[0].get("analysis_id"), latest["analysis_id"]) if history else latest["analysis_id"],
            "latest_score": latest["disaster_recovery_governance_score"],
            "score_history": _history_points(scores),
            "recovery_state_history": [item.get("recovery_state_history", []) for item in history],
        }
        return {
            "status": latest["disaster_recovery_governance_status"],
            "disaster_recovery_governance_status": latest["disaster_recovery_governance_status"],
            "disaster_recovery_governance_authority": latest["disaster_recovery_governance_authority"],
            "disaster_recovery_governance_score": latest["disaster_recovery_governance_score"],
            "disaster_recovery_governance_grade": latest["disaster_recovery_governance_grade"],
            **latest,
            "latest_disaster_recovery_governance": latest,
            "disaster_recovery_governance_history": history,
            "disaster_recovery_governance_history_summary": summary,
            "summary_counts": latest["summary_counts"],
            "warnings": latest["warnings"],
        }

    def latest_disaster_recovery_governance(self) -> Dict[str, Any]:
        return self.list_disaster_recovery_governance(limit=1)

    def disaster_recovery_governance_history(self, limit: int = 20) -> Dict[str, Any]:
        latest = self.list_disaster_recovery_governance(limit=limit)
        history = latest["disaster_recovery_governance_history"]
        return {
            "status": latest["status"],
            "disaster_recovery_governance_status": latest["disaster_recovery_governance_status"],
            "disaster_recovery_governance_authority": latest["disaster_recovery_governance_authority"],
            "disaster_recovery_governance_score": latest["disaster_recovery_governance_score"],
            "disaster_recovery_governance_grade": latest["disaster_recovery_governance_grade"],
            "count": len(history),
            "disaster_recovery_governance_history": history,
            "disaster_recovery_governance_history_summary": latest["disaster_recovery_governance_history_summary"],
            "summary_counts": latest["summary_counts"],
            "warnings": latest["warnings"],
        }
