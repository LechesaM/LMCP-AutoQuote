from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
import re
from typing import Any, Dict, List, Optional

from app.services.multi_tenant_governance_service import MultiTenantGovernanceService
from app.services.operational_exception_service import _safe_dict, _safe_int, _safe_list, _safe_str
from app.services.production_supervision_command_service import ProductionSupervisionCommandService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
K8S_ROOT = PROJECT_ROOT / "k8s"
BASE_DIR = K8S_ROOT / "base"
STAGING_DIR = K8S_ROOT / "overlays" / "staging"
PRODUCTION_DIR = K8S_ROOT / "overlays" / "production"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "ok", "ready", "enabled", "placeholder"}
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


def _extract_env_int(text: str, env_name: str) -> int:
    match = re.search(rf"name:\s*{re.escape(env_name)}.*?value:\s*\"?(\d+)\"?", text, re.S)
    return int(match.group(1)) if match else 0


class BackupRestoreGovernanceService:
    def __init__(
        self,
        k8s_root: Optional[Path] = None,
        supervision_command_service: Optional[ProductionSupervisionCommandService] = None,
        multi_tenant_governance_service: Optional[MultiTenantGovernanceService] = None,
    ) -> None:
        self.k8s_root = k8s_root or K8S_ROOT
        self.base_dir = self.k8s_root / "base"
        self.staging_dir = self.k8s_root / "overlays" / "staging"
        self.production_dir = self.k8s_root / "overlays" / "production"
        self.supervision_command_service = supervision_command_service or ProductionSupervisionCommandService()
        self.multi_tenant_governance_service = multi_tenant_governance_service or MultiTenantGovernanceService(k8s_root=self.k8s_root)

    def _manifest_paths(self) -> Dict[str, Path]:
        return {
            "kustomization": self.base_dir / "kustomization.yaml",
            "namespace": self.base_dir / "namespace.yaml",
            "configmap": self.base_dir / "configmap.yaml",
            "secret_placeholders": self.base_dir / "secret-placeholders.yaml",
            "postgres_backup_cronjob": self.base_dir / "postgres-backup-cronjob-placeholder.yaml",
            "redis_persistence": self.base_dir / "redis-persistence-placeholder.yaml",
            "backup_storage_secret": self.base_dir / "backup-storage-secret-placeholder.yaml",
            "restore_rehearsal_job": self.base_dir / "restore-rehearsal-job-placeholder.yaml",
            "backup_retention_policy": self.base_dir / "backup-retention-policy-placeholder.yaml",
            "persistent_volume_claims": self.base_dir / "persistent-volume-claims.yaml",
            "tenant_namespace_template": self.base_dir / "tenant-namespace-template.yaml",
            "tenant_network_policy": self.base_dir / "tenant-network-policy-template.yaml",
            "tenant_rbac_placeholder": self.base_dir / "tenant-rbac-placeholder.yaml",
            "tenant_resource_quota_placeholder": self.base_dir / "tenant-resource-quota-placeholder.yaml",
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
        secret_text = self._text(self.base_dir / "backup-storage-secret-placeholder.yaml")
        all_text = "\n".join(
            self._text(path)
            for path in self.k8s_root.rglob("*")
            if path.is_file() and path.suffix.lower() in {".yaml", ".yml", ".md"}
        )
        return {
            "final_automation_disabled": 'LMCP_ALLOW_FINAL_AUTOMATION: "false"' in production_text,
            "dry_run_mode_enabled": 'LMCP_DRY_RUN_MODE: "true"' in production_text,
            "human_supervision_required": 'LMCP_REQUIRE_HUMAN_SUPERVISION: "true"' in production_text,
            "submission_lock_required": "LMCP_SUBMISSION_LOCK_FILE:" in production_text,
            "production_overlay_separated_from_staging": "LMCP_ENV: staging" in staging_text and "LMCP_ENV: production" in production_text,
            "embedded_credentials_found": any(
                marker in all_text for marker in ["BEGIN PRIVATE KEY", "AKIA", "ghp_", "sk-", "xoxb-", "real-password", "prod-password", "password123"]
            ),
            "live_external_storage_credentials_found": any(
                marker in all_text.lower() for marker in ["aws_secret_access_key", "aws_access_key_id", "s3://", "gs://", "azblob", "minio-prod", "bucket-prod"]
            ),
            "backup_storage_secret_placeholder_only": _contains_all(secret_text, ["backup-storage-secret-placeholder", "placeholder", "backup_endpoint", "backup_access_key", "backup_secret_key"]) and not any(
                marker in secret_text for marker in ["BEGIN PRIVATE KEY", "AKIA", "ghp_", "sk-", "xoxb-", "real-password", "prod-password", "password123"]
            ),
        }

    def _postgres_backup_readiness(self) -> Dict[str, Any]:
        text = self._text(self.base_dir / "postgres-backup-cronjob-placeholder.yaml")
        rpo_minutes = _extract_env_int(text, "rpo_minutes")
        ready = _contains_all(text, ["postgres-backup-cronjob-placeholder", "kind: CronJob", "pg_dump", "backup_schedule", "rpo_minutes"])
        return {
            "ready": ready,
            "schedule": _safe_str(re.search(r"schedule:\s*\"([^\"]+)\"", text).group(1), "placeholder") if re.search(r"schedule:\s*\"([^\"]+)\"", text) else "placeholder",
            "rpo_minutes": rpo_minutes,
        }

    def _redis_persistence_readiness(self) -> Dict[str, Any]:
        text = self._text(self.base_dir / "redis-persistence-placeholder.yaml")
        ready = _contains_all(text, ["redis-persistence-placeholder", "PersistentVolumeClaim", "persistence_enabled", "backup_safe"])
        return {
            "ready": ready,
            "persistence_enabled": "persistence_enabled" in text,
            "backup_safe": "backup_safe" in text,
        }

    def _restore_rehearsal_readiness(self) -> Dict[str, Any]:
        text = self._text(self.base_dir / "restore-rehearsal-job-placeholder.yaml")
        rto_minutes = _extract_env_int(text, "rto_minutes")
        ready = _contains_all(text, ["restore-rehearsal-job-placeholder", "kind: Job", "restore_validation", "rto_minutes"])
        return {
            "ready": ready,
            "rto_minutes": rto_minutes,
            "restore_validation": "restore_validation" in text,
        }

    def _backup_retention_governance(self) -> Dict[str, Any]:
        text = self._text(self.base_dir / "backup-retention-policy-placeholder.yaml")
        ready = _contains_all(text, ["backup-retention-policy-placeholder", "retention_days", "retention_policy", "rpo_minutes", "rto_minutes"])
        return {
            "ready": ready,
            "retention_days": _extract_int(text, r'retention_days:\s*"?(\d+)"?'),
            "rpo_minutes": _extract_int(text, r'rpo_minutes:\s*"?(\d+)"?'),
            "rto_minutes": _extract_int(text, r'rto_minutes:\s*"?(\d+)"?'),
        }

    def _tenant_boundaries(self) -> Dict[str, Any]:
        multi_tenant = _safe_dict(self.multi_tenant_governance_service.latest_multi_tenant_governance())
        safety_model = _safe_dict(multi_tenant.get("safety_model"))
        tenant_isolation = _safe_dict(multi_tenant.get("tenant_isolation_readiness"))
        namespace = _safe_dict(multi_tenant.get("namespace_segregation_readiness"))
        workload = _safe_dict(multi_tenant.get("tenant_workload_separation"))
        storage = _safe_dict(multi_tenant.get("storage_isolation_readiness"))
        ingress = _safe_dict(multi_tenant.get("ingress_tenancy_segregation"))
        supervision = _safe_dict(multi_tenant.get("supervision_tenancy_coverage"))
        leakage = _safe_dict(multi_tenant.get("cross_tenant_leakage_indicators"))
        ready = all(
            [
                _truthy(tenant_isolation.get("ready")),
                _truthy(namespace.get("ready")),
                _truthy(workload.get("ready")),
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
            "storage_isolation_ready": _truthy(storage.get("ready")),
            "ingress_tenancy_segregation_ready": _truthy(ingress.get("ready")),
            "supervision_tenancy_coverage_ready": _truthy(supervision.get("ready")),
            "cross_tenant_leakage_safe": _truthy(leakage.get("cross_tenant_leakage_safe")),
            "tenant_onboarding_disabled": _truthy(safety_model.get("tenant_onboarding_disabled")),
        }

    def _saturation_indicators(self) -> Dict[str, Any]:
        supervision_snapshot = _safe_dict(self.supervision_command_service.latest_supervision_command())
        workload = _safe_dict(supervision_snapshot.get("operational_workload_visibility"))
        saturation = _safe_dict(supervision_snapshot.get("supervision_saturation"))
        active_sessions = _safe_int(workload.get("active_session_count"), 0)
        assigned_rfq_count = _safe_int(workload.get("assigned_rfq_count"), 0)
        pending_approval_count = _safe_int(workload.get("pending_approval_count"), 0)
        workload_items = _safe_int(workload.get("workload_items"), assigned_rfq_count + pending_approval_count)
        queue_backlog_count = _safe_int(saturation.get("queue_backlog_count"), 0)
        worker_backlog_count = _safe_int(saturation.get("worker_backlog_count"), 0)
        saturation_active = _truthy(saturation.get("supervision_saturation_active")) or active_sessions > 1 or workload_items > 2 or queue_backlog_count > 0 or worker_backlog_count > 0
        return {
            "supervision_saturation_active": saturation_active,
            "workload_pressure": _safe_str(workload.get("workload_pressure"), "low"),
            "active_session_count": active_sessions,
            "assigned_rfq_count": assigned_rfq_count,
            "pending_approval_count": pending_approval_count,
            "workload_items": workload_items,
            "queue_backlog_count": queue_backlog_count,
            "worker_backlog_count": worker_backlog_count,
        }

    def _snapshot(self) -> Dict[str, Any]:
        paths = self._manifest_paths()
        safety = self._safety_model()
        missing_files = [name for name, path in paths.items() if not self._file_ready(path)]

        postgres_backup = self._postgres_backup_readiness()
        redis_persistence = self._redis_persistence_readiness()
        restore_rehearsal = self._restore_rehearsal_readiness()
        retention = self._backup_retention_governance()
        tenant_boundaries = self._tenant_boundaries()
        saturation = self._saturation_indicators()

        backup_storage_secret = _safe_str(self._text(paths["backup_storage_secret"]).strip(), "")
        encrypted_backup_placeholder_ready = safety["backup_storage_secret_placeholder_only"] and "encryption" in self._text(paths["backup_storage_secret"]).lower()

        backup_ready = postgres_backup["ready"] and redis_persistence["ready"] and retention["ready"] and safety["backup_storage_secret_placeholder_only"]
        restore_ready = restore_rehearsal["ready"] and tenant_boundaries["ready"] and safety["dry_run_mode_enabled"] and safety["human_supervision_required"]
        backup_boundaries_ready = tenant_boundaries["ready"] and safety["production_overlay_separated_from_staging"]
        backup_governance_ready = all(
            [
                backup_ready,
                restore_ready,
                backup_boundaries_ready,
                encrypted_backup_placeholder_ready,
                retention["ready"],
                postgres_backup["rpo_minutes"] > 0,
                restore_rehearsal["rto_minutes"] > 0,
            ]
        )

        restore_blockers = _dedupe(
            ([] if postgres_backup["ready"] else ["PostgreSQL backup placeholder is incomplete"]) +
            ([] if redis_persistence["ready"] else ["Redis persistence placeholder is incomplete"]) +
            ([] if restore_rehearsal["ready"] else ["restore rehearsal job placeholder is incomplete"]) +
            ([] if retention["ready"] else ["backup retention policy placeholder is incomplete"]) +
            ([] if safety["backup_storage_secret_placeholder_only"] else ["backup storage secret is not placeholder-only"]) +
            ([] if tenant_boundaries["ready"] else ["tenant-aware backup boundaries are incomplete"]) +
            ([] if safety["dry_run_mode_enabled"] else ["dry-run mode is not enabled"]) +
            ([] if safety["human_supervision_required"] else ["human supervision is not mandatory"]) +
            ([] if not safety["live_external_storage_credentials_found"] else ["live external storage credentials were detected"]) +
            ([] if postgres_backup["rpo_minutes"] > 0 else ["RPO visibility is missing"]) +
            ([] if restore_rehearsal["rto_minutes"] > 0 else ["RTO visibility is missing"])
        )

        backup_degradation = {
            "postgres_backup_degradation": not postgres_backup["ready"],
            "redis_persistence_degradation": not redis_persistence["ready"],
            "restore_rehearsal_degradation": not restore_rehearsal["ready"],
            "retention_governance_degradation": not retention["ready"],
            "encrypted_backup_placeholder_degradation": not encrypted_backup_placeholder_ready,
            "tenant_boundary_degradation": not tenant_boundaries["ready"],
            "backup_saturation_degradation": _truthy(saturation.get("supervision_saturation_active")),
        }

        blocker_sources = [
            {
                "source": "postgres_backup_cronjob_placeholder",
                "ready": postgres_backup["ready"],
                "blockers": [] if postgres_backup["ready"] else ["postgres backup cronjob placeholder is incomplete"],
            },
            {
                "source": "redis_persistence_placeholder",
                "ready": redis_persistence["ready"],
                "blockers": [] if redis_persistence["ready"] else ["redis persistence placeholder is incomplete"],
            },
            {
                "source": "backup_storage_secret_placeholder",
                "ready": safety["backup_storage_secret_placeholder_only"],
                "blockers": [] if safety["backup_storage_secret_placeholder_only"] else ["backup storage secret includes non-placeholder content"],
            },
            {
                "source": "restore_rehearsal_job_placeholder",
                "ready": restore_rehearsal["ready"],
                "blockers": [] if restore_rehearsal["ready"] else ["restore rehearsal job placeholder is incomplete"],
            },
            {
                "source": "backup_retention_policy_placeholder",
                "ready": retention["ready"],
                "blockers": [] if retention["ready"] else ["backup retention policy placeholder is incomplete"],
            },
            {
                "source": "tenant_aware_backup_boundaries",
                "ready": tenant_boundaries["ready"],
                "blockers": [] if tenant_boundaries["ready"] else ["tenant-aware backup boundaries are incomplete"],
            },
            {
                "source": "supervision_coverage",
                "ready": not _truthy(saturation.get("supervision_saturation_active")),
                "blockers": [] if not _truthy(saturation.get("supervision_saturation_active")) else ["supervision saturation is active"],
            },
        ]

        unresolved_blockers = _dedupe([blocker for source in blocker_sources for blocker in _safe_list(source.get("blockers"))] + restore_blockers)
        warnings = _dedupe(
            _safe_list(safety.get("warnings"))
            + unresolved_blockers
            + (["backup saturation remains visible"] if _truthy(saturation.get("supervision_saturation_active")) else [])
        )

        component_scores = [
            100.0 if postgres_backup["ready"] else 0.0,
            100.0 if redis_persistence["ready"] else 0.0,
            100.0 if restore_rehearsal["ready"] else 0.0,
            100.0 if retention["ready"] else 0.0,
            100.0 if safety["backup_storage_secret_placeholder_only"] else 0.0,
            100.0 if encrypted_backup_placeholder_ready else 0.0,
            100.0 if tenant_boundaries["ready"] else 0.0,
            100.0 if postgres_backup["rpo_minutes"] > 0 else 0.0,
            100.0 if restore_rehearsal["rto_minutes"] > 0 else 0.0,
            100.0 if not _truthy(saturation.get("supervision_saturation_active")) else 40.0,
            100.0 if backup_governance_ready else 0.0,
        ]
        base_score = round(mean(component_scores), 2) if component_scores else 0.0
        deduction = (len(unresolved_blockers) * 5.0) + (len(warnings) * 1.5)
        score_after_deductions = max(0.0, round(base_score - deduction, 2))

        if unresolved_blockers:
            recovery_state = "unresolved-blocked"
            backup_score = min(score_after_deductions, 69.99)
        elif warnings or _truthy(saturation.get("supervision_saturation_active")) or not backup_governance_ready:
            recovery_state = "degraded-but-recovering"
            backup_score = min(max(score_after_deductions, 70.0), 84.99)
        else:
            recovery_state = "recovered"
            backup_score = max(score_after_deductions, 90.0)

        backup_score = round(min(backup_score, 100.0), 2)
        backup_status = _status_from_score(backup_score)
        if recovery_state == "unresolved-blocked":
            backup_status = "blocked"
        elif recovery_state == "degraded-but-recovering":
            backup_status = "watch"
        else:
            backup_status = "ok"
        backup_authority = _authority_from_status(backup_status)
        backup_grade = "ready" if recovery_state == "recovered" else "watch" if recovery_state == "degraded-but-recovering" else "blocked"
        recovery_state_history = [
            {
                "analysis_id": "backup-restore-governance:latest",
                "generated_at": _now_iso(),
                "recovery_state": recovery_state,
                "backup_restore_governance_score": backup_score,
                "backup_restore_governance_status": backup_status,
                "backup_restore_governance_authority": backup_authority,
                "unresolved_blocker_count": len(unresolved_blockers),
            }
        ]
        recovery_rationale = {
            "state": recovery_state,
            "summary": (
                "Backup, restore, and durability controls are fully recovered."
                if recovery_state == "recovered"
                else "Backup controls are degraded but the staging topology is still converging."
                if recovery_state == "degraded-but-recovering"
                else "Backup recovery blockers remain unresolved."
            ),
            "score_impact": {
                "base_score": round(base_score, 2),
                "deductions": round(deduction, 2),
                "final_score": backup_score,
            },
            "state_basis": {
                "postgres_backup_ready": postgres_backup["ready"],
                "redis_persistence_ready": redis_persistence["ready"],
                "restore_rehearsal_ready": restore_rehearsal["ready"],
                "backup_retention_ready": retention["ready"],
                "encrypted_backup_placeholder_ready": encrypted_backup_placeholder_ready,
                "tenant_boundaries_ready": tenant_boundaries["ready"],
                "rpo_minutes": postgres_backup["rpo_minutes"],
                "rto_minutes": restore_rehearsal["rto_minutes"],
                "restore_blocker_count": len(unresolved_blockers),
            },
        }
        history_entry = {
            "analysis_id": "backup-restore-governance:latest",
            "generated_at": _now_iso(),
            "backup_restore_governance_status": backup_status,
            "backup_restore_governance_authority": backup_authority,
            "backup_restore_governance_score": backup_score,
            "backup_restore_governance_grade": backup_grade,
            "recovery_state": recovery_state,
            "recovery_state_history": recovery_state_history,
            "unresolved_blockers": unresolved_blockers,
            "recovery_rationale": recovery_rationale,
            "blocker_sources": blocker_sources,
            "postgres_backup_readiness": _component(postgres_backup["ready"], postgres_backup),
            "redis_persistence_readiness": _component(redis_persistence["ready"], redis_persistence),
            "restore_rehearsal_readiness": _component(restore_rehearsal["ready"], restore_rehearsal),
            "backup_retention_governance": _component(retention["ready"], retention),
            "encrypted_backup_placeholder_governance": _component(encrypted_backup_placeholder_ready, {"placeholder_only": safety["backup_storage_secret_placeholder_only"]}),
            "tenant_aware_backup_boundaries": _component(tenant_boundaries["ready"], tenant_boundaries),
            "rpo_visibility": {"ready": postgres_backup["rpo_minutes"] > 0, "rpo_minutes": postgres_backup["rpo_minutes"]},
            "rto_visibility": {"ready": restore_rehearsal["rto_minutes"] > 0, "rto_minutes": restore_rehearsal["rto_minutes"]},
            "backup_degradation_indicators": backup_degradation,
            "restore_blocker_indicators": {f"blocker_{index}": blocker for index, blocker in enumerate(unresolved_blockers, start=1)},
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

    def list_backup_restore_governance(self, limit: int = 20) -> Dict[str, Any]:
        latest = self._snapshot()
        history = self._history(limit=limit)
        scores = [float(item.get("backup_restore_governance_score", 0.0)) for item in history] or [latest["backup_restore_governance_score"]]
        summary = {
            "analysis_count": len(history),
            "latest_analysis_id": _safe_str(history[0].get("analysis_id"), latest["analysis_id"]) if history else latest["analysis_id"],
            "latest_score": latest["backup_restore_governance_score"],
            "score_history": _history_points(scores),
            "recovery_state_history": [item.get("recovery_state_history", []) for item in history],
        }
        return {
            "status": latest["backup_restore_governance_status"],
            "backup_restore_governance_status": latest["backup_restore_governance_status"],
            "backup_restore_governance_authority": latest["backup_restore_governance_authority"],
            "backup_restore_governance_score": latest["backup_restore_governance_score"],
            "backup_restore_governance_grade": latest["backup_restore_governance_grade"],
            **latest,
            "latest_backup_restore_governance": latest,
            "backup_governance_history": history,
            "backup_governance_history_summary": summary,
            "summary_counts": latest["summary_counts"],
            "warnings": latest["warnings"],
        }

    def latest_backup_restore_governance(self) -> Dict[str, Any]:
        return self.list_backup_restore_governance(limit=1)

    def backup_restore_governance_history(self, limit: int = 20) -> Dict[str, Any]:
        latest = self.list_backup_restore_governance(limit=limit)
        history = latest["backup_governance_history"]
        return {
            "status": latest["status"],
            "backup_restore_governance_status": latest["backup_restore_governance_status"],
            "backup_restore_governance_authority": latest["backup_restore_governance_authority"],
            "backup_restore_governance_score": latest["backup_restore_governance_score"],
            "backup_restore_governance_grade": latest["backup_restore_governance_grade"],
            "count": len(history),
            "backup_governance_history": history,
            "backup_governance_history_summary": latest["backup_governance_history_summary"],
            "summary_counts": latest["summary_counts"],
            "warnings": latest["warnings"],
        }
