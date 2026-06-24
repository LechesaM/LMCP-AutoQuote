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


def _extract_hpa_bounds(text: str) -> Dict[str, int]:
    min_match = re.search(r"minReplicas:\s*(\d+)", text)
    max_match = re.search(r"maxReplicas:\s*(\d+)", text)
    return {
        "min_replicas": int(min_match.group(1)) if min_match else 0,
        "max_replicas": int(max_match.group(1)) if max_match else 0,
    }


class AutoscalingGovernanceService:
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
            "persistent_volume_claims": self.base_dir / "persistent-volume-claims.yaml",
            "backend_hpa": self.base_dir / "backend-hpa-placeholder.yaml",
            "frontend_hpa": self.base_dir / "frontend-hpa-placeholder.yaml",
            "worker_hpa": self.base_dir / "worker-hpa-placeholder.yaml",
            "resource_quota": self.base_dir / "resource-quota-placeholder.yaml",
            "limit_range": self.base_dir / "limit-range-placeholder.yaml",
            "queue_depth_scaling": self.base_dir / "queue-depth-scaling-placeholder.yaml",
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
        alert_text = self._text(self.base_dir / "alertmanager-placeholder.yaml")
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
            "external_alert_delivery_disabled": not any(
                marker in alert_text.lower() for marker in ["webhook_configs", "email_configs", "slack", "pagerduty", "opsgenie", "victorops", "pushover", "telegram_configs"]
            ),
            "autonomous_production_authority_introduced": 'LMCP_ALLOW_FINAL_AUTOMATION: "true"' in all_text,
        }

    def _deployment_resources(self, path: Path) -> Dict[str, Any]:
        text = self._text(path)
        requests_ready = _contains_all(text, ["resources:", "requests:", "cpu:", "memory:"])
        limits_ready = _contains_all(text, ["resources:", "limits:", "cpu:", "memory:"])
        return {
            "ready": requests_ready and limits_ready,
            "requests_ready": requests_ready,
            "limits_ready": limits_ready,
            "resource_requests_governed": requests_ready,
            "resource_limits_governed": limits_ready,
        }

    def _hpa_details(self, path: Path) -> Dict[str, Any]:
        text = self._text(path)
        bounds = _extract_hpa_bounds(text)
        target_name = path.name.replace("-hpa-placeholder.yaml", "")
        ready = path.exists() and _contains_all(
            text,
            [
                "apiVersion: autoscaling/v2",
                "kind: HorizontalPodAutoscaler",
                f"name: {path.stem}",
                f"name: {target_name}",
                "minReplicas:",
                "maxReplicas:",
            ],
        ) and bounds["max_replicas"] >= max(1, bounds["min_replicas"])
        return {
            "ready": ready,
            "target_name": target_name,
            **bounds,
        }

    def _queue_depth_scaling(self) -> Dict[str, Any]:
        path = self.base_dir / "queue-depth-scaling-placeholder.yaml"
        text = self._text(path)
        return {
            "ready": path.exists() and _contains_all(text, ["queue-depth-scaling-placeholder", "queue_depth_metric", "scale_up_threshold", "scale_down_threshold"]),
            "metric_source": "queue-depth-scaling-placeholder" if path.exists() else "missing",
            "queue_depth_metric": "placeholder" if "queue_depth_metric" in text else "",
            "scale_up_threshold": "placeholder" if "scale_up_threshold" in text else "",
            "scale_down_threshold": "placeholder" if "scale_down_threshold" in text else "",
        }

    def _tenant_boundaries(self) -> Dict[str, Any]:
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
        degradation = _safe_dict(multi_tenant.get("tenant_degradation_indicators"))
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
            "tenant_degradation_indicators": degradation,
            "safety_model": safety_model,
        }

    def _saturation_indicators(self, supervision_snapshot: Dict[str, Any]) -> Dict[str, Any]:
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

        backend_resources = self._deployment_resources(paths["backend_deployment"])
        frontend_resources = self._deployment_resources(paths["frontend_deployment"])
        worker_resources = self._deployment_resources(paths["worker_deployment"])
        resource_requests_ready = all(
            [backend_resources["requests_ready"], frontend_resources["requests_ready"], worker_resources["requests_ready"]]
        )
        resource_limits_ready = all([backend_resources["limits_ready"], frontend_resources["limits_ready"], worker_resources["limits_ready"]])
        resource_governance_ready = resource_requests_ready and resource_limits_ready

        backend_hpa = self._hpa_details(paths["backend_hpa"])
        frontend_hpa = self._hpa_details(paths["frontend_hpa"])
        worker_hpa = self._hpa_details(paths["worker_hpa"])
        hpa_ready = all([backend_hpa["ready"], frontend_hpa["ready"], worker_hpa["ready"]])

        resource_quota_text = self._text(paths["resource_quota"])
        limit_range_text = self._text(paths["limit_range"])
        queue_depth = self._queue_depth_scaling()
        tenant_boundaries = self._tenant_boundaries()
        supervision_snapshot = _safe_dict(self.supervision_command_service.latest_supervision_command())
        saturation_indicators = self._saturation_indicators(supervision_snapshot)
        saturation_active = _truthy(saturation_indicators.get("supervision_saturation_active"))

        resource_quota_ready = _contains_all(resource_quota_text, ["resource-quota-placeholder", "requests.cpu", "requests.memory", "limits.cpu", "limits.memory"])
        limit_range_ready = _contains_all(limit_range_text, ["limit-range-placeholder", "defaultRequest", "default", "requests.cpu", "requests.memory", "limits.cpu", "limits.memory"])
        resource_governance_ready = resource_requests_ready and resource_limits_ready and resource_quota_ready and limit_range_ready

        backend_autoscaling_ready = backend_hpa["ready"] and backend_resources["ready"] and resource_governance_ready
        frontend_autoscaling_ready = frontend_hpa["ready"] and frontend_resources["ready"] and resource_governance_ready
        worker_autoscaling_ready = worker_hpa["ready"] and worker_resources["ready"] and queue_depth["ready"] and resource_governance_ready
        queue_depth_scaling_ready = queue_depth["ready"] and _safe_int(saturation_indicators.get("queue_backlog_count"), 0) >= 0
        scale_up_governance_ready = all([backend_hpa["max_replicas"] > backend_hpa["min_replicas"], frontend_hpa["max_replicas"] > frontend_hpa["min_replicas"], worker_hpa["max_replicas"] > worker_hpa["min_replicas"], queue_depth_scaling_ready, resource_governance_ready])
        scale_down_governance_ready = all([backend_hpa["min_replicas"] >= 1, frontend_hpa["min_replicas"] >= 1, worker_hpa["min_replicas"] >= 1, safety["dry_run_mode_enabled"], safety["human_supervision_required"], resource_governance_ready])

        readiness_map = {
            "hpa_readiness": hpa_ready,
            "worker_autoscaling_readiness": worker_autoscaling_ready,
            "backend_autoscaling_readiness": backend_autoscaling_ready,
            "frontend_autoscaling_readiness": frontend_autoscaling_ready,
            "cpu_memory_request_governance": resource_requests_ready,
            "cpu_memory_limit_governance": resource_limits_ready,
            "resource_governance": resource_governance_ready,
            "queue_depth_scaling_readiness": queue_depth_scaling_ready,
            "tenant_aware_scaling_boundaries": tenant_boundaries["ready"],
            "scale_up_governance": scale_up_governance_ready,
            "scale_down_governance": scale_down_governance_ready,
            "production_safety_controls": all(
                [
                    safety["final_automation_disabled"],
                    safety["dry_run_mode_enabled"],
                    safety["human_supervision_required"],
                    safety["submission_lock_required"],
                    safety["production_overlay_separated_from_staging"],
                    not safety["autonomous_production_authority_introduced"],
                    safety["external_alert_delivery_disabled"],
                ]
            ),
        }
        degradation_indicators = {
            "hpa_degradation": not hpa_ready,
            "worker_autoscaling_degradation": not worker_autoscaling_ready,
            "backend_autoscaling_degradation": not backend_autoscaling_ready,
            "frontend_autoscaling_degradation": not frontend_autoscaling_ready,
            "cpu_memory_request_degradation": not resource_requests_ready,
            "cpu_memory_limit_degradation": not resource_limits_ready,
            "queue_depth_scaling_degradation": not queue_depth_scaling_ready,
            "tenant_boundary_degradation": not tenant_boundaries["ready"],
            "scale_up_degradation": not scale_up_governance_ready,
            "scale_down_degradation": not scale_down_governance_ready,
            "saturation_degradation": saturation_active,
            "production_safety_degradation": not readiness_map["production_safety_controls"],
        }

        blocker_sources = [
            {
                "source": "hpa_placeholders",
                "ready": hpa_ready,
                "blockers": _dedupe(
                    ([] if backend_hpa["ready"] else ["backend HPA placeholder is incomplete"]) +
                    ([] if frontend_hpa["ready"] else ["frontend HPA placeholder is incomplete"]) +
                    ([] if worker_hpa["ready"] else ["worker HPA placeholder is incomplete"])
                ),
            },
            {
            "source": "resource_governance",
                "ready": resource_governance_ready,
                "blockers": _dedupe(
                    ([] if resource_requests_ready else ["CPU and memory requests are not represented on all workloads"]) +
                    ([] if resource_limits_ready else ["CPU and memory limits are not represented on all workloads"]) +
                    ([] if resource_quota_ready else ["resource quota placeholder is incomplete"]) +
                    ([] if limit_range_ready else ["limit range placeholder is incomplete"])
                ),
            },
            {
                "source": "queue_depth_scaling_placeholder",
                "ready": queue_depth_scaling_ready,
                "blockers": [] if queue_depth_scaling_ready else ["queue-depth scaling placeholder is incomplete"],
            },
            {
                "source": "tenant_aware_scaling_boundaries",
                "ready": tenant_boundaries["ready"],
                "blockers": _dedupe(
                    ([] if tenant_boundaries["tenant_isolation_ready"] else ["tenant isolation readiness is incomplete"]) +
                    ([] if tenant_boundaries["namespace_segregation_ready"] else ["namespace segregation readiness is incomplete"]) +
                    ([] if tenant_boundaries["tenant_workload_separation_ready"] else ["tenant workload separation is incomplete"]) +
                    ([] if tenant_boundaries["rbac_tenant_boundaries_ready"] else ["RBAC tenant boundaries are incomplete"]) +
                    ([] if tenant_boundaries["storage_isolation_ready"] else ["storage isolation readiness is incomplete"]) +
                    ([] if tenant_boundaries["ingress_tenancy_segregation_ready"] else ["ingress tenancy segregation is incomplete"]) +
                    ([] if tenant_boundaries["supervision_tenancy_coverage_ready"] else ["supervision tenancy coverage is incomplete"]) +
                    ([] if tenant_boundaries["cross_tenant_leakage_safe"] else ["cross-tenant leakage indicators are not safe"])
                ),
            },
            {
                "source": "production_safety_controls",
                "ready": readiness_map["production_safety_controls"],
                "blockers": _dedupe(
                    ([] if safety["final_automation_disabled"] else ["final automation is not disabled"]) +
                    ([] if safety["dry_run_mode_enabled"] else ["dry-run mode is not enabled"]) +
                    ([] if safety["human_supervision_required"] else ["human supervision is not mandatory"]) +
                    ([] if safety["submission_lock_required"] else ["submission lock enforcement is missing"]) +
                    ([] if safety["production_overlay_separated_from_staging"] else ["production overlay is not separated from staging"]) +
                    ([] if safety["external_alert_delivery_disabled"] else ["external alert delivery is still enabled"]) +
                    ([] if not safety["autonomous_production_authority_introduced"] else ["autonomous production authority was introduced"])
                ),
            },
            {
                "source": "supervision_coverage",
                "ready": not saturation_active,
                "blockers": [] if not saturation_active else ["workload saturation indicators are active"],
            },
        ]

        unresolved_blockers = _dedupe([blocker for source in blocker_sources for blocker in _safe_list(source.get("blockers"))])
        warnings = _dedupe(
            _safe_list(safety.get("warnings"))
            + unresolved_blockers
            + (["workload pressure is elevated"] if saturation_active else [])
            + (["queue backlog remains visible"] if _safe_int(saturation_indicators.get("queue_backlog_count"), 0) > 0 else [])
            + (["worker backlog remains visible"] if _safe_int(saturation_indicators.get("worker_backlog_count"), 0) > 0 else [])
        )

        component_scores = [
            100.0 if hpa_ready else 0.0,
            100.0 if worker_autoscaling_ready else 0.0,
            100.0 if backend_autoscaling_ready else 0.0,
            100.0 if frontend_autoscaling_ready else 0.0,
            100.0 if resource_requests_ready else 0.0,
            100.0 if resource_limits_ready else 0.0,
            100.0 if resource_governance_ready else 0.0,
            100.0 if queue_depth_scaling_ready else 0.0,
            100.0 if tenant_boundaries["ready"] else 0.0,
            100.0 if scale_up_governance_ready else 0.0,
            100.0 if scale_down_governance_ready else 0.0,
            100.0 if not saturation_active else 40.0,
            100.0 if not any(_truthy(value) for value in degradation_indicators.values()) else 35.0,
            100.0 if readiness_map["production_safety_controls"] else 0.0,
        ]
        base_score = round(mean(component_scores), 2) if component_scores else 0.0
        deduction = (len(unresolved_blockers) * 5.0) + (len(warnings) * 1.5)
        score_after_deductions = max(0.0, round(base_score - deduction, 2))

        if unresolved_blockers:
            recovery_state = "unresolved-blocked"
            autoscaling_score = min(score_after_deductions, 69.99)
        elif warnings or saturation_active or any(_truthy(value) for value in degradation_indicators.values()) or not all(readiness_map.values()):
            recovery_state = "degraded-but-recovering"
            autoscaling_score = min(max(score_after_deductions, 70.0), 84.99)
        else:
            recovery_state = "recovered"
            autoscaling_score = max(score_after_deductions, 90.0)

        autoscaling_score = round(min(autoscaling_score, 100.0), 2)
        autoscaling_status = _status_from_score(autoscaling_score)
        if recovery_state == "unresolved-blocked":
            autoscaling_status = "blocked"
        elif recovery_state == "degraded-but-recovering":
            autoscaling_status = "watch"
        else:
            autoscaling_status = "ok"
        autoscaling_authority = _authority_from_status(autoscaling_status)
        autoscaling_grade = "ready" if recovery_state == "recovered" else "watch" if recovery_state == "degraded-but-recovering" else "blocked"
        recovery_state_history = [
            {
                "analysis_id": "autoscaling-governance:latest",
                "generated_at": _now_iso(),
                "recovery_state": recovery_state,
                "autoscaling_governance_score": autoscaling_score,
                "autoscaling_governance_status": autoscaling_status,
                "autoscaling_governance_authority": autoscaling_authority,
                "unresolved_blocker_count": len(unresolved_blockers),
            }
        ]
        recovery_rationale = {
            "state": recovery_state,
            "summary": (
                "Autoscaling and resource controls are fully recovered."
                if recovery_state == "recovered"
                else "Autoscaling controls are degraded but the staging package is still converging."
                if recovery_state == "degraded-but-recovering"
                else "Autoscaling recovery blockers remain unresolved."
            ),
            "score_impact": {
                "base_score": round(base_score, 2),
                "deductions": round(deduction, 2),
                "final_score": autoscaling_score,
            },
            "state_basis": {
                "hpa_ready": hpa_ready,
                "worker_autoscaling_ready": worker_autoscaling_ready,
                "backend_autoscaling_ready": backend_autoscaling_ready,
                "frontend_autoscaling_ready": frontend_autoscaling_ready,
                "cpu_memory_request_governance_ready": resource_requests_ready,
                "cpu_memory_limit_governance_ready": resource_limits_ready,
                "resource_governance_ready": resource_governance_ready,
                "queue_depth_scaling_ready": queue_depth_scaling_ready,
                "tenant_aware_scaling_boundaries_ready": tenant_boundaries["ready"],
                "scale_up_governance_ready": scale_up_governance_ready,
                "scale_down_governance_ready": scale_down_governance_ready,
                "supervision_saturation_active": saturation_active,
                "unresolved_blocker_count": len(unresolved_blockers),
            },
        }
        history_entry = {
            "analysis_id": "autoscaling-governance:latest",
            "generated_at": _now_iso(),
            "autoscaling_governance_status": autoscaling_status,
            "autoscaling_governance_authority": autoscaling_authority,
            "autoscaling_governance_score": autoscaling_score,
            "autoscaling_governance_grade": autoscaling_grade,
            "recovery_state": recovery_state,
            "recovery_state_history": recovery_state_history,
            "unresolved_blockers": unresolved_blockers,
            "recovery_rationale": recovery_rationale,
            "blocker_sources": blocker_sources,
            "hpa_readiness": _component(hpa_ready, {"backend": backend_hpa, "frontend": frontend_hpa, "worker": worker_hpa}),
            "worker_autoscaling_readiness": _component(worker_autoscaling_ready, {"hpa": worker_hpa, "resources": worker_resources}),
            "backend_autoscaling_readiness": _component(backend_autoscaling_ready, {"hpa": backend_hpa, "resources": backend_resources}),
            "frontend_autoscaling_readiness": _component(frontend_autoscaling_ready, {"hpa": frontend_hpa, "resources": frontend_resources}),
            "cpu_memory_request_governance": _component(resource_requests_ready, {"backend": backend_resources, "frontend": frontend_resources, "worker": worker_resources}),
            "cpu_memory_limit_governance": _component(resource_limits_ready, {"backend": backend_resources, "frontend": frontend_resources, "worker": worker_resources}),
            "resource_governance": _component(resource_governance_ready, {"resource_quota_ready": resource_quota_ready, "limit_range_ready": limit_range_ready}),
            "queue_depth_scaling_readiness": _component(queue_depth_scaling_ready, queue_depth),
            "tenant_aware_scaling_boundaries": _component(tenant_boundaries["ready"], tenant_boundaries),
            "scale_up_governance": _component(scale_up_governance_ready, {"backend_hpa": backend_hpa, "frontend_hpa": frontend_hpa, "worker_hpa": worker_hpa}),
            "scale_down_governance": _component(scale_down_governance_ready, {"backend_hpa": backend_hpa, "frontend_hpa": frontend_hpa, "worker_hpa": worker_hpa}),
            "autoscaling_saturation_indicators": saturation_indicators,
            "autoscaling_degradation_indicators": degradation_indicators,
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

    def list_autoscaling_governance(self, limit: int = 20) -> Dict[str, Any]:
        latest = self._snapshot()
        history = self._history(limit=limit)
        scores = [float(item.get("autoscaling_governance_score", 0.0)) for item in history] or [latest["autoscaling_governance_score"]]
        summary = {
            "analysis_count": len(history),
            "latest_analysis_id": _safe_str(history[0].get("analysis_id"), latest["analysis_id"]) if history else latest["analysis_id"],
            "latest_score": latest["autoscaling_governance_score"],
            "score_history": _history_points(scores),
            "recovery_state_history": [item.get("recovery_state_history", []) for item in history],
        }
        return {
            "status": latest["autoscaling_governance_status"],
            "autoscaling_governance_status": latest["autoscaling_governance_status"],
            "autoscaling_governance_authority": latest["autoscaling_governance_authority"],
            "autoscaling_governance_score": latest["autoscaling_governance_score"],
            "autoscaling_governance_grade": latest["autoscaling_governance_grade"],
            **latest,
            "latest_autoscaling_governance": latest,
            "autoscaling_governance_history": history,
            "autoscaling_governance_history_summary": summary,
            "summary_counts": latest["summary_counts"],
            "warnings": latest["warnings"],
        }

    def latest_autoscaling_governance(self) -> Dict[str, Any]:
        return self.list_autoscaling_governance(limit=1)

    def autoscaling_governance_history(self, limit: int = 20) -> Dict[str, Any]:
        latest = self.list_autoscaling_governance(limit=limit)
        history = latest["autoscaling_governance_history"]
        return {
            "status": latest["status"],
            "autoscaling_governance_status": latest["autoscaling_governance_status"],
            "autoscaling_governance_authority": latest["autoscaling_governance_authority"],
            "autoscaling_governance_score": latest["autoscaling_governance_score"],
            "autoscaling_governance_grade": latest["autoscaling_governance_grade"],
            "count": len(history),
            "autoscaling_governance_history": history,
            "autoscaling_governance_history_summary": latest["autoscaling_governance_history_summary"],
            "summary_counts": latest["summary_counts"],
            "warnings": latest["warnings"],
        }
