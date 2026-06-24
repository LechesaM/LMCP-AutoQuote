from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.operational_exception_service import _read_json, _safe_dict, _safe_float, _safe_int, _safe_list, _safe_str
from app.services.multi_tenant_governance_service import MultiTenantGovernanceService
from app.services.production_operationalization_service import ProductionOperationalizationService
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
        return value.strip().lower() in {"true", "1", "yes", "y", "ok", "ready", "enabled"}
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


class DistributedObservabilityGovernanceService:
    def __init__(
        self,
        k8s_root: Optional[Path] = None,
        production_operationalization_service: Optional[ProductionOperationalizationService] = None,
        supervision_command_service: Optional[ProductionSupervisionCommandService] = None,
        multi_tenant_governance_service: Optional[MultiTenantGovernanceService] = None,
    ) -> None:
        self.k8s_root = k8s_root or K8S_ROOT
        self.base_dir = self.k8s_root / "base"
        self.staging_dir = self.k8s_root / "overlays" / "staging"
        self.production_dir = self.k8s_root / "overlays" / "production"
        self.production_operationalization_service = production_operationalization_service or ProductionOperationalizationService()
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
            "pvc": self.base_dir / "persistent-volume-claims.yaml",
            "loki_placeholder": self.base_dir / "loki-placeholder.yaml",
            "tempo_placeholder": self.base_dir / "tempo-placeholder.yaml",
            "distributed_prometheus_placeholder": self.base_dir / "distributed-prometheus-placeholder.yaml",
            "alertmanager_placeholder": self.base_dir / "alertmanager-placeholder.yaml",
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
        loki_text = self._text(self.base_dir / "loki-placeholder.yaml")
        tempo_text = self._text(self.base_dir / "tempo-placeholder.yaml")
        prom_text = self._text(self.base_dir / "distributed-prometheus-placeholder.yaml")
        alert_text = self._text(self.base_dir / "alertmanager-placeholder.yaml")
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
            "loki_placeholder_present": "loki-placeholder" in loki_text and "placeholder" in loki_text,
            "tempo_placeholder_present": "tempo-placeholder" in tempo_text and "placeholder" in tempo_text,
            "distributed_prometheus_placeholder_present": "distributed-prometheus-placeholder" in prom_text and "placeholder" in prom_text,
            "alertmanager_placeholder_present": "alertmanager-placeholder" in alert_text and "placeholder" in alert_text,
            "cross_tenant_telemetry_isolation_ready": _truthy(_safe_dict(self.multi_tenant_governance_service.latest_multi_tenant_governance()).get("cross_tenant_leakage_indicators", {}).get("cross_tenant_leakage_safe")),
            "embedded_credentials_found": any(
                marker in all_text for marker in ["BEGIN PRIVATE KEY", "AKIA", "ghp_", "sk-", "xoxb-", "real-password", "prod-password", "password123"]
            ),
            "live_telemetry_endpoints_found": any(marker in all_text.lower() for marker in ["http://", "https://", "grafana.com", "example.com", "webhook_configs:"]),
            "external_alert_delivery_found": any(marker in alert_text.lower() for marker in ["slack", "pagerduty", "opsgenie", "webhook_configs", "email_configs", "victorops", "pushover", "telegram_configs"]),
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
            "k8s/base/loki-placeholder.yaml",
            "k8s/base/tempo-placeholder.yaml",
            "k8s/base/distributed-prometheus-placeholder.yaml",
            "k8s/base/alertmanager-placeholder.yaml",
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

        prod_ops = _safe_dict(self.production_operationalization_service.latest_production_governance())
        observability_governance = _safe_dict(prod_ops.get("production_observability_governance"))
        observability_readiness = _safe_dict(observability_governance.get("observability_readiness_indicators"))
        observability_risk = _safe_dict(observability_governance.get("observability_risk_indicators"))
        tenant_isolation = _safe_dict(prod_ops.get("production_runtime_segmentation", {})).get("tenant_workspace_isolation", {})
        supervision = _safe_dict(self.supervision_command_service.latest_supervision_command())
        supervision_coverage = _safe_dict(supervision.get("supervision_coverage"))
        workload = _safe_dict(supervision.get("operational_workload_visibility"))
        saturation = _safe_dict(supervision.get("supervision_saturation"))
        multi_tenant = _safe_dict(self.multi_tenant_governance_service.latest_multi_tenant_governance())

        telemetry_aggregation_ready = all(
            [
                safety["loki_placeholder_present"],
                safety["distributed_prometheus_placeholder_present"],
                observability_readiness.get("worker_heartbeat") is True,
                observability_readiness.get("system_resilience") is True,
                _safe_float(observability_governance.get("production_observability_governance_score"), 0.0) >= 85.0,
            ]
        )
        distributed_metrics_ready = safety["distributed_prometheus_placeholder_present"] and safety["dry_run_mode_enabled"]
        centralized_log_governance_ready = safety["loki_placeholder_present"] and not safety["external_alert_delivery_found"]
        tracing_ready = safety["tempo_placeholder_present"] and telemetry_aggregation_ready
        observability_shard_ready = safety["distributed_prometheus_placeholder_present"] and safety["tempo_placeholder_present"] and safety["loki_placeholder_present"]
        tenant_telemetry_isolation_ready = _truthy(tenant_isolation.get("isolation_verified")) or _truthy(multi_tenant.get("cross_tenant_leakage_indicators", {}).get("cross_tenant_leakage_safe"))
        observability_failover_ready = _truthy(_safe_dict(prod_ops.get("high_availability_governance")).get("ha_readiness_indicators", {}).get("queue_stable")) and _truthy(_safe_dict(prod_ops.get("disaster_recovery_governance")).get("recovery_readiness_indicators", {}).get("final_readiness_cleared"))
        alert_governance_ready = safety["alertmanager_placeholder_present"] and not safety["external_alert_delivery_found"]

        readiness_map = {
            "telemetry_aggregation_readiness": telemetry_aggregation_ready,
            "distributed_metrics_readiness": distributed_metrics_ready,
            "centralized_log_governance_readiness": centralized_log_governance_ready,
            "tracing_readiness": tracing_ready,
            "observability_shard_readiness": observability_shard_ready,
            "tenant_telemetry_isolation": tenant_telemetry_isolation_ready,
            "observability_failover_readiness": observability_failover_ready,
            "alert_governance_readiness": alert_governance_ready,
        }
        degradation_indicators = {key.replace("_readiness", "_degradation"): not value for key, value in readiness_map.items()}
        degradation_indicators["observability_governance_degradation"] = not all(readiness_map.values())

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
        if safety["embedded_credentials_found"]:
            blockers.append("embedded credentials were detected in the observability package")
        if safety["live_telemetry_endpoints_found"]:
            blockers.append("live telemetry endpoints are not permitted")
        if safety["external_alert_delivery_found"]:
            blockers.append("external alert delivery is not permitted")

        warnings: List[str] = []
        if not telemetry_aggregation_ready:
            warnings.append("Telemetry aggregation readiness is not yet complete.")
        if not distributed_metrics_ready:
            warnings.append("Distributed metrics readiness is not yet complete.")
        if not centralized_log_governance_ready:
            warnings.append("Centralized log-governance readiness is not yet complete.")
        if not tracing_ready:
            warnings.append("Tracing readiness is not yet complete.")
        if not observability_shard_ready:
            warnings.append("Observability shard readiness is not yet complete.")
        if not tenant_telemetry_isolation_ready:
            warnings.append("Tenant telemetry isolation is not yet complete.")
        if not observability_failover_ready:
            warnings.append("Observability failover readiness is not yet complete.")
        if not alert_governance_ready:
            warnings.append("Alert-governance readiness is not yet complete.")

        blocker_sources = [
            {"source": "loki_placeholder", "ready": safety["loki_placeholder_present"], "blockers": [] if safety["loki_placeholder_present"] else ["Loki placeholder is missing"]},
            {"source": "tempo_placeholder", "ready": safety["tempo_placeholder_present"], "blockers": [] if safety["tempo_placeholder_present"] else ["Tempo placeholder is missing"]},
            {"source": "distributed_prometheus_placeholder", "ready": safety["distributed_prometheus_placeholder_present"], "blockers": [] if safety["distributed_prometheus_placeholder_present"] else ["Distributed Prometheus placeholder is missing"]},
            {"source": "alertmanager_placeholder", "ready": safety["alertmanager_placeholder_present"], "blockers": [] if safety["alertmanager_placeholder_present"] else ["Alertmanager placeholder is missing"]},
            {"source": "alert_delivery_controls", "ready": not safety["external_alert_delivery_found"], "blockers": [] if not safety["external_alert_delivery_found"] else ["External alert delivery is enabled"]},
        ]

        component_scores = [100.0 if value else 0.0 for value in readiness_map.values()]
        base_score = round(mean(component_scores), 2) if component_scores else 0.0
        deduction = round((len(blockers) * 6.0) + (len(warnings) * 1.5), 2)
        score_after_deductions = max(0.0, round(base_score - deduction, 2))
        if blockers:
            recovery_state = "unresolved-blocked"
            observability_score = min(score_after_deductions, 69.99)
        elif warnings or not all(readiness_map.values()):
            recovery_state = "degraded-but-recovering"
            observability_score = min(max(score_after_deductions, 70.0), 84.99)
        else:
            recovery_state = "recovered"
            observability_score = max(score_after_deductions, 90.0)
        observability_score = round(min(observability_score, 100.0), 2)

        status = _status_from_score(observability_score)
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
                "analysis_id": "distributed-observability",
                "generated_at": _now_iso(),
                "recovery_state": recovery_state,
                "distributed_observability_status": status,
                "distributed_observability_authority": authority,
                "distributed_observability_score": observability_score,
                "unresolved_blocker_count": len(blockers),
            }
        ]
        recovery_rationale = {
            "state": recovery_state,
            "summary": (
                "Distributed observability governance is fully recovered."
                if recovery_state == "recovered"
                else "Distributed observability governance is degraded but still progressing."
                if recovery_state == "degraded-but-recovering"
                else "Distributed observability governance remains blocked by unresolved safety issues."
            ),
            "score_impact": {"base_score": base_score, "deductions": deduction, "final_score": observability_score},
            "state_basis": {
                "telemetry_aggregation_ready": telemetry_aggregation_ready,
                "distributed_metrics_ready": distributed_metrics_ready,
                "centralized_log_governance_ready": centralized_log_governance_ready,
                "tracing_ready": tracing_ready,
                "observability_shard_ready": observability_shard_ready,
                "tenant_telemetry_isolation_ready": tenant_telemetry_isolation_ready,
                "observability_failover_ready": observability_failover_ready,
                "alert_governance_ready": alert_governance_ready,
                "unresolved_blocker_count": len(blockers),
            },
        }

        latest_distributed_observability = {
            "analysis_id": "distributed-observability:latest",
            "generated_at": _now_iso(),
            "status": status,
            "distributed_observability_status": status,
            "distributed_observability_authority": authority,
            "distributed_observability_score": observability_score,
            "distributed_observability_grade": grade,
            "recovery_state": recovery_state,
            "recovery_state_history": recovery_state_history,
            "unresolved_blockers": blockers,
            "recovery_rationale": recovery_rationale,
            "blocker_sources": blocker_sources,
            "telemetry_aggregation_readiness": self._component(telemetry_aggregation_ready),
            "distributed_metrics_readiness": self._component(distributed_metrics_ready),
            "centralized_log_governance_readiness": self._component(centralized_log_governance_ready),
            "tracing_readiness": self._component(tracing_ready),
            "observability_shard_readiness": self._component(observability_shard_ready),
            "tenant_telemetry_isolation": self._component(tenant_telemetry_isolation_ready),
            "observability_failover_readiness": self._component(observability_failover_ready),
            "alert_governance_readiness": self._component(alert_governance_ready),
            "observability_degradation_indicators": degradation_indicators,
            "manifest_inventory": inventory,
            "safety_model": safety,
            "warnings": warnings,
        }
        latest_distributed_observability["distributed_observability_governance_history"] = recovery_state_history
        return latest_distributed_observability

    def _history(self, limit: int = 20) -> List[Dict[str, Any]]:
        latest = self._snapshot()
        return [
            {
                "analysis_id": latest["analysis_id"],
                "generated_at": latest["generated_at"],
                "distributed_observability_status": latest["distributed_observability_status"],
                "distributed_observability_authority": latest["distributed_observability_authority"],
                "distributed_observability_score": latest["distributed_observability_score"],
                "distributed_observability_grade": latest["distributed_observability_grade"],
                "recovery_state": latest["recovery_state"],
                "recovery_state_history": latest["recovery_state_history"],
                "unresolved_blockers": latest["unresolved_blockers"],
                "recovery_rationale": latest["recovery_rationale"],
                "blocker_sources": latest["blocker_sources"],
            }
        ][: max(1, int(limit))]

    def list_distributed_observability(self, limit: int = 20) -> Dict[str, Any]:
        latest = self._snapshot()
        history = self._history(limit=limit)
        scores = [float(item.get("distributed_observability_score", 0.0)) for item in history] or [latest["distributed_observability_score"]]
        summary = {
            "analysis_count": len(history),
            "latest_analysis_id": _safe_str(history[0].get("analysis_id"), latest["analysis_id"]) if history else latest["analysis_id"],
            "latest_score": latest["distributed_observability_score"],
            "score_history": _history_points(scores),
            "recovery_state_history": [item.get("recovery_state_history", []) for item in history],
        }
        return {
            "status": latest["status"],
            "distributed_observability_status": latest["distributed_observability_status"],
            "distributed_observability_authority": latest["distributed_observability_authority"],
            "distributed_observability_score": latest["distributed_observability_score"],
            "distributed_observability_grade": latest["distributed_observability_grade"],
            **latest,
            "latest_distributed_observability": latest,
            "distributed_observability_history": history,
            "distributed_observability_history_summary": summary,
            "summary_counts": {
                "PASS": 1 if latest["recovery_state"] == "recovered" else 0,
                "WARN": 1 if latest["recovery_state"] == "degraded-but-recovering" else 0,
                "FAIL": 1 if latest["recovery_state"] == "unresolved-blocked" else 0,
            },
            "warnings": latest["warnings"],
        }

    def latest_distributed_observability(self) -> Dict[str, Any]:
        return self.list_distributed_observability(limit=1)

    def distributed_observability_history(self, limit: int = 20) -> Dict[str, Any]:
        latest = self.list_distributed_observability(limit=limit)
        history = latest["distributed_observability_history"]
        return {
            "status": latest["status"],
            "distributed_observability_status": latest["distributed_observability_status"],
            "distributed_observability_authority": latest["distributed_observability_authority"],
            "distributed_observability_score": latest["distributed_observability_score"],
            "distributed_observability_grade": latest["distributed_observability_grade"],
            "count": len(history),
            "distributed_observability_history": history,
            "distributed_observability_history_summary": latest["distributed_observability_history_summary"],
            "summary_counts": latest["summary_counts"],
            "warnings": latest["warnings"],
        }
