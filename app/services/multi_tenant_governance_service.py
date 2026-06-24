from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.operational_exception_service import _safe_dict, _safe_int, _safe_list, _safe_str


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
        return value.strip().lower() in {"true", "1", "yes", "y", "ok", "ready", "enabled", "isolated"}
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


class MultiTenantGovernanceService:
    def __init__(self, k8s_root: Optional[Path] = None) -> None:
        self.k8s_root = k8s_root or K8S_ROOT
        self.base_dir = self.k8s_root / "base"
        self.staging_dir = self.k8s_root / "overlays" / "staging"
        self.production_dir = self.k8s_root / "overlays" / "production"

    def _manifest_paths(self) -> Dict[str, Path]:
        return {
            "kustomization": self.base_dir / "kustomization.yaml",
            "namespace": self.base_dir / "namespace.yaml",
            "configmap": self.base_dir / "configmap.yaml",
            "secret_placeholders": self.base_dir / "secret-placeholders.yaml",
            "backend_deployment": self.base_dir / "backend-deployment.yaml",
            "backend_service": self.base_dir / "backend-service.yaml",
            "frontend_deployment": self.base_dir / "frontend-deployment.yaml",
            "frontend_service": self.base_dir / "frontend-service.yaml",
            "worker_deployment": self.base_dir / "worker-deployment.yaml",
            "redis_deployment": self.base_dir / "redis-deployment.yaml",
            "redis_service": self.base_dir / "redis-service.yaml",
            "postgres_statefulset": self.base_dir / "postgres-statefulset.yaml",
            "postgres_service": self.base_dir / "postgres-service.yaml",
            "prometheus_deployment": self.base_dir / "prometheus-deployment.yaml",
            "prometheus_service": self.base_dir / "prometheus-service.yaml",
            "grafana_deployment": self.base_dir / "grafana-deployment.yaml",
            "grafana_service": self.base_dir / "grafana-service.yaml",
            "network_policy": self.base_dir / "network-policy.yaml",
            "pvc": self.base_dir / "persistent-volume-claims.yaml",
            "tenant_namespace_template": self.base_dir / "tenant-namespace-template.yaml",
            "tenant_network_policies": self.base_dir / "tenant-network-policy-template.yaml",
            "tenant_rbac_placeholders": self.base_dir / "tenant-rbac-placeholder.yaml",
            "tenant_resource_quota_placeholders": self.base_dir / "tenant-resource-quota-placeholder.yaml",
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
        production_patch = self._text(self.production_dir / "patches" / "production-safety-patch.yaml")
        staging_patch = self._text(self.staging_dir / "patches" / "staging-safety-patch.yaml")
        tenant_namespace = self._text(self.base_dir / "tenant-namespace-template.yaml")
        tenant_rbac = self._text(self.base_dir / "tenant-rbac-placeholder.yaml")
        tenant_quota = self._text(self.base_dir / "tenant-resource-quota-placeholder.yaml")
        tenant_network = self._text(self.base_dir / "tenant-network-policy-template.yaml")
        all_text = "\n".join(
            self._text(path)
            for path in self.k8s_root.rglob("*")
            if path.is_file() and path.suffix.lower() in {".yaml", ".yml", ".md"}
        )
        return {
            "final_automation_disabled": 'LMCP_ALLOW_FINAL_AUTOMATION: "false"' in production_patch,
            "dry_run_mode_enabled": 'LMCP_DRY_RUN_MODE: "true"' in production_patch,
            "human_supervision_required": 'LMCP_REQUIRE_HUMAN_SUPERVISION: "true"' in production_patch,
            "submission_lock_required": "LMCP_SUBMISSION_LOCK_FILE:" in production_patch,
            "production_overlay_separated_from_staging": "LMCP_ENV: staging" in staging_patch and "LMCP_ENV: production" in production_patch,
            "tenant_namespace_template_present": "tenant-namespace-template-placeholder" in tenant_namespace and 'lmcp.io/tenant-segregation: "enabled"' in tenant_namespace,
            "tenant_network_policy_present": "tenant-network-policy-template-placeholder" in tenant_network and "policyTypes" in tenant_network,
            "tenant_rbac_placeholder_present": "tenant-rbac-placeholder" in tenant_rbac and "verbs:" in tenant_rbac,
            "tenant_resource_quota_placeholder_present": "tenant-resource-quota-placeholder" in tenant_quota and "requests.cpu" in tenant_quota,
            "tenant_onboarding_disabled": 'lmcp.io/tenant-onboarding: "disabled"' in tenant_namespace,
            "embedded_credentials_found": any(
                marker in all_text for marker in ["BEGIN PRIVATE KEY", "AKIA", "ghp_", "sk-", "xoxb-", "real-password", "prod-password", "password123"]
            ),
        }

    def _manifest_inventory(self) -> Dict[str, List[str]]:
        base_files = [
            "k8s/base/backend-deployment.yaml",
            "k8s/base/backend-service.yaml",
            "k8s/base/frontend-deployment.yaml",
            "k8s/base/frontend-service.yaml",
            "k8s/base/worker-deployment.yaml",
            "k8s/base/redis-deployment.yaml",
            "k8s/base/redis-service.yaml",
            "k8s/base/postgres-statefulset.yaml",
            "k8s/base/postgres-service.yaml",
            "k8s/base/prometheus-deployment.yaml",
            "k8s/base/prometheus-service.yaml",
            "k8s/base/grafana-deployment.yaml",
            "k8s/base/grafana-service.yaml",
            "k8s/base/network-policy.yaml",
            "k8s/base/persistent-volume-claims.yaml",
            "k8s/base/configmap.yaml",
            "k8s/base/secret-placeholders.yaml",
            "k8s/base/tenant-namespace-template.yaml",
            "k8s/base/tenant-network-policy-template.yaml",
            "k8s/base/tenant-rbac-placeholder.yaml",
            "k8s/base/tenant-resource-quota-placeholder.yaml",
        ]
        overlay_files = [
            "k8s/overlays/staging/kustomization.yaml",
            "k8s/overlays/staging/patches/staging-safety-patch.yaml",
            "k8s/overlays/production/kustomization.yaml",
            "k8s/overlays/production/patches/production-safety-patch.yaml",
        ]
        return {
            "base_files": [path for path in base_files if (self.k8s_root / path.replace("k8s/", "")).exists()],
            "overlay_files": [path for path in overlay_files if (self.k8s_root / path.replace("k8s/", "")).exists()],
        }

    def _component(self, ready: bool, evidence: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"ready": ready, "status": "PASS" if ready else "WARN", "score": 100.0 if ready else 0.0, "evidence": evidence or {}}

    def _snapshot(self) -> Dict[str, Any]:
        paths = self._manifest_paths()
        safety = self._safety_model()
        inventory = self._manifest_inventory()

        missing_files = [name for name, path in paths.items() if not self._file_ready(path)]
        tenant_isolation_ready = all(
            [
                safety["tenant_namespace_template_present"],
                safety["tenant_network_policy_present"],
                safety["tenant_rbac_placeholder_present"],
                safety["tenant_resource_quota_placeholder_present"],
                safety["tenant_onboarding_disabled"],
            ]
        )
        namespace_segregation_ready = safety["tenant_namespace_template_present"] and safety["tenant_resource_quota_placeholder_present"]
        tenant_workload_separation_ready = safety["tenant_network_policy_present"] and safety["tenant_resource_quota_placeholder_present"]
        rbac_tenant_boundaries_ready = safety["tenant_rbac_placeholder_present"] and not safety["embedded_credentials_found"]
        storage_isolation_ready = safety["tenant_resource_quota_placeholder_present"] and self._file_ready(paths["pvc"])
        ingress_tenancy_segregation_ready = safety["tenant_network_policy_present"] and safety["tenant_namespace_template_present"]
        supervision_tenancy_coverage_ready = safety["dry_run_mode_enabled"] and safety["human_supervision_required"] and safety["submission_lock_required"]
        cross_tenant_leakage_safe = all(
            [
                safety["tenant_onboarding_disabled"],
                not safety["embedded_credentials_found"],
                safety["production_overlay_separated_from_staging"],
            ]
        )

        readiness_map = {
            "tenant_isolation_readiness": tenant_isolation_ready,
            "namespace_segregation_readiness": namespace_segregation_ready,
            "tenant_workload_separation": tenant_workload_separation_ready,
            "rbac_tenant_boundaries": rbac_tenant_boundaries_ready,
            "storage_isolation_readiness": storage_isolation_ready,
            "ingress_tenancy_segregation": ingress_tenancy_segregation_ready,
            "supervision_tenancy_coverage": supervision_tenancy_coverage_ready,
            "cross_tenant_leakage_indicators": cross_tenant_leakage_safe,
        }
        degradation_indicators = {key.replace("_readiness", "_degradation").replace("_indicators", "_degradation"): not value for key, value in readiness_map.items()}
        degradation_indicators["cross_tenant_leakage_degradation"] = not cross_tenant_leakage_safe

        blockers: List[str] = []
        if missing_files:
            blockers.append(f"missing manifest files: {', '.join(sorted(missing_files))}")
        if not safety["final_automation_disabled"]:
            blockers.append("final automation must remain disabled")
        if not safety["dry_run_mode_enabled"]:
            blockers.append("dry-run mode must remain enabled")
        if not safety["human_supervision_required"]:
            blockers.append("human supervision must remain mandatory")
        if not safety["submission_lock_required"]:
            blockers.append("submission lock enforcement is missing")
        if not safety["production_overlay_separated_from_staging"]:
            blockers.append("production overlay is not separated from staging")
        if not safety["tenant_onboarding_disabled"]:
            blockers.append("tenant onboarding is not explicitly disabled")
        if safety["embedded_credentials_found"]:
            blockers.append("embedded credentials were detected in the tenant governance package")

        warnings: List[str] = []
        if not tenant_isolation_ready:
            warnings.append("Tenant isolation readiness is not yet complete.")
        if not namespace_segregation_ready:
            warnings.append("Namespace segregation readiness is not yet complete.")
        if not tenant_workload_separation_ready:
            warnings.append("Tenant workload separation is not yet complete.")
        if not rbac_tenant_boundaries_ready:
            warnings.append("RBAC tenant boundaries are not yet complete.")
        if not storage_isolation_ready:
            warnings.append("Storage isolation readiness is not yet complete.")
        if not ingress_tenancy_segregation_ready:
            warnings.append("Ingress tenancy segregation is not yet complete.")
        if not supervision_tenancy_coverage_ready:
            warnings.append("Supervision tenancy coverage is not yet complete.")
        if not cross_tenant_leakage_safe:
            warnings.append("Cross-tenant leakage indicators remain elevated.")

        blocker_sources = [
            {"source": "tenant_namespace_templates", "ready": safety["tenant_namespace_template_present"], "blockers": [] if safety["tenant_namespace_template_present"] else ["tenant namespace template placeholder is missing"]},
            {"source": "tenant_network_policies", "ready": safety["tenant_network_policy_present"], "blockers": [] if safety["tenant_network_policy_present"] else ["tenant network policy placeholder is missing"]},
            {"source": "tenant_rbac_placeholders", "ready": safety["tenant_rbac_placeholder_present"], "blockers": [] if safety["tenant_rbac_placeholder_present"] else ["tenant RBAC placeholder is missing"]},
            {"source": "tenant_resource_quota_placeholders", "ready": safety["tenant_resource_quota_placeholder_present"], "blockers": [] if safety["tenant_resource_quota_placeholder_present"] else ["tenant resource quota placeholder is missing"]},
            {"source": "tenant_onboarding_controls", "ready": safety["tenant_onboarding_disabled"], "blockers": [] if safety["tenant_onboarding_disabled"] else ["tenant onboarding is not explicitly disabled"]},
        ]

        component_scores = [100.0 if value else 0.0 for value in readiness_map.values()]
        base_score = round(mean(component_scores), 2) if component_scores else 0.0
        deduction = round((len(blockers) * 6.0) + (len(warnings) * 1.5), 2)
        score_after_deductions = max(0.0, round(base_score - deduction, 2))
        if blockers:
            recovery_state = "unresolved-blocked"
            tenant_score = min(score_after_deductions, 69.99)
        elif warnings or not all(readiness_map.values()):
            recovery_state = "degraded-but-recovering"
            tenant_score = min(max(score_after_deductions, 70.0), 84.99)
        else:
            recovery_state = "recovered"
            tenant_score = max(score_after_deductions, 90.0)
        tenant_score = round(min(tenant_score, 100.0), 2)

        status = _status_from_score(tenant_score)
        if recovery_state == "unresolved-blocked":
            status = "blocked"
        elif recovery_state == "degraded-but-recovering":
            status = "watch"
        else:
            status = "ok"
        authority = _authority_from_status(status)
        grade = "ready" if recovery_state == "recovered" else "watch" if recovery_state == "degraded-but-recovering" else "blocked"

        recovery_state_history = [
            {
                "analysis_id": "multi-tenant-governance",
                "generated_at": _now_iso(),
                "recovery_state": recovery_state,
                "multi_tenant_governance_status": status,
                "multi_tenant_governance_authority": authority,
                "multi_tenant_governance_score": tenant_score,
                "unresolved_blocker_count": len(blockers),
            }
        ]
        recovery_rationale = {
            "state": recovery_state,
            "summary": (
                "Tenant isolation governance is fully recovered."
                if recovery_state == "recovered"
                else "Tenant isolation governance is degraded but still progressing."
                if recovery_state == "degraded-but-recovering"
                else "Tenant isolation governance remains blocked by unresolved safety issues."
            ),
            "score_impact": {"base_score": base_score, "deductions": deduction, "final_score": tenant_score},
            "state_basis": {
                "tenant_isolation_ready": tenant_isolation_ready,
                "namespace_segregation_ready": namespace_segregation_ready,
                "tenant_workload_separation_ready": tenant_workload_separation_ready,
                "rbac_tenant_boundaries_ready": rbac_tenant_boundaries_ready,
                "storage_isolation_ready": storage_isolation_ready,
                "ingress_tenancy_segregation_ready": ingress_tenancy_segregation_ready,
                "supervision_tenancy_coverage_ready": supervision_tenancy_coverage_ready,
                "cross_tenant_leakage_safe": cross_tenant_leakage_safe,
                "unresolved_blocker_count": len(blockers),
            },
        }

        latest_multi_tenant_governance = {
            "analysis_id": "multi-tenant-governance:latest",
            "generated_at": _now_iso(),
            "status": status,
            "multi_tenant_governance_status": status,
            "multi_tenant_governance_authority": authority,
            "multi_tenant_governance_score": tenant_score,
            "multi_tenant_governance_grade": grade,
            "recovery_state": recovery_state,
            "recovery_state_history": recovery_state_history,
            "unresolved_blockers": blockers,
            "recovery_rationale": recovery_rationale,
            "blocker_sources": blocker_sources,
            "tenant_isolation_readiness": self._component(tenant_isolation_ready),
            "namespace_segregation_readiness": self._component(namespace_segregation_ready),
            "tenant_workload_separation": self._component(tenant_workload_separation_ready),
            "rbac_tenant_boundaries": self._component(rbac_tenant_boundaries_ready),
            "storage_isolation_readiness": self._component(storage_isolation_ready),
            "ingress_tenancy_segregation": self._component(ingress_tenancy_segregation_ready),
            "supervision_tenancy_coverage": self._component(supervision_tenancy_coverage_ready),
            "cross_tenant_leakage_indicators": {
                "tenant_onboarding_disabled": safety["tenant_onboarding_disabled"],
                "embedded_credentials_found": safety["embedded_credentials_found"],
                "production_overlay_separated_from_staging": safety["production_overlay_separated_from_staging"],
                "cross_tenant_leakage_safe": cross_tenant_leakage_safe,
            },
            "tenant_degradation_indicators": degradation_indicators,
            "manifest_inventory": inventory,
            "safety_model": safety,
            "warnings": warnings,
        }
        latest_multi_tenant_governance["multi_tenant_governance_history"] = recovery_state_history
        return latest_multi_tenant_governance

    def _history(self, limit: int = 20) -> List[Dict[str, Any]]:
        latest = self._snapshot()
        return [
            {
                "analysis_id": latest["analysis_id"],
                "generated_at": latest["generated_at"],
                "multi_tenant_governance_status": latest["multi_tenant_governance_status"],
                "multi_tenant_governance_authority": latest["multi_tenant_governance_authority"],
                "multi_tenant_governance_score": latest["multi_tenant_governance_score"],
                "multi_tenant_governance_grade": latest["multi_tenant_governance_grade"],
                "recovery_state": latest["recovery_state"],
                "recovery_state_history": latest["recovery_state_history"],
                "unresolved_blockers": latest["unresolved_blockers"],
                "recovery_rationale": latest["recovery_rationale"],
                "blocker_sources": latest["blocker_sources"],
            }
        ][: max(1, int(limit))]

    def list_multi_tenant_governance(self, limit: int = 20) -> Dict[str, Any]:
        latest = self._snapshot()
        history = self._history(limit=limit)
        scores = [float(item.get("multi_tenant_governance_score", 0.0)) for item in history] or [latest["multi_tenant_governance_score"]]
        summary = {
            "analysis_count": len(history),
            "latest_analysis_id": _safe_str(history[0].get("analysis_id"), latest["analysis_id"]) if history else latest["analysis_id"],
            "latest_score": latest["multi_tenant_governance_score"],
            "score_history": _history_points(scores),
            "recovery_state_history": [item.get("recovery_state_history", []) for item in history],
        }
        return {
            "status": latest["status"],
            "multi_tenant_governance_status": latest["multi_tenant_governance_status"],
            "multi_tenant_governance_authority": latest["multi_tenant_governance_authority"],
            "multi_tenant_governance_score": latest["multi_tenant_governance_score"],
            "multi_tenant_governance_grade": latest["multi_tenant_governance_grade"],
            **latest,
            "latest_multi_tenant_governance": latest,
            "multi_tenant_governance_history": history,
            "multi_tenant_governance_history_summary": summary,
            "summary_counts": {
                "PASS": 1 if latest["recovery_state"] == "recovered" else 0,
                "WARN": 1 if latest["recovery_state"] == "degraded-but-recovering" else 0,
                "FAIL": 1 if latest["recovery_state"] == "unresolved-blocked" else 0,
            },
            "warnings": latest["warnings"],
        }

    def latest_multi_tenant_governance(self) -> Dict[str, Any]:
        return self.list_multi_tenant_governance(limit=1)

    def multi_tenant_governance_history(self, limit: int = 20) -> Dict[str, Any]:
        latest = self.list_multi_tenant_governance(limit=limit)
        history = latest["multi_tenant_governance_history"]
        return {
            "status": latest["status"],
            "multi_tenant_governance_status": latest["multi_tenant_governance_status"],
            "multi_tenant_governance_authority": latest["multi_tenant_governance_authority"],
            "multi_tenant_governance_score": latest["multi_tenant_governance_score"],
            "multi_tenant_governance_grade": latest["multi_tenant_governance_grade"],
            "count": len(history),
            "multi_tenant_governance_history": history,
            "multi_tenant_governance_history_summary": latest["multi_tenant_governance_history_summary"],
            "summary_counts": latest["summary_counts"],
            "warnings": latest["warnings"],
        }
