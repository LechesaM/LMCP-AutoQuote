from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional
import re

from app.services.operational_exception_service import _read_json, _safe_dict, _safe_float, _safe_int, _safe_list, _safe_str
from app.services.production_operationalization_service import ProductionOperationalizationService
from app.services.production_supervision_command_service import ProductionSupervisionCommandService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
K8S_ROOT = PROJECT_ROOT / "k8s"
BASE_DIR = K8S_ROOT / "base"
STAGING_DIR = K8S_ROOT / "overlays" / "staging"
PRODUCTION_DIR = K8S_ROOT / "overlays" / "production"
STAGING_PATCH = STAGING_DIR / "patches" / "staging-safety-patch.yaml"
PRODUCTION_PATCH = PRODUCTION_DIR / "patches" / "production-safety-patch.yaml"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: Any) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(_safe_str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


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


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "ok", "pass", "ready", "certified"}
    return bool(value)


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _extract_replicas(text: str) -> int:
    match = re.search(r"(?m)^\s*replicas:\s*(\d+)\s*$", text)
    return int(match.group(1)) if match else 0


def _dedupe(values: List[str]) -> List[str]:
    cleaned: List[str] = []
    for value in values:
        text = _safe_str(value)
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


class HaTopologyGovernanceService:
    def __init__(
        self,
        k8s_root: Optional[Path] = None,
        production_operationalization_service: Optional[ProductionOperationalizationService] = None,
        supervision_command_service: Optional[ProductionSupervisionCommandService] = None,
    ) -> None:
        self.k8s_root = k8s_root or K8S_ROOT
        self.base_dir = self.k8s_root / "base"
        self.staging_dir = self.k8s_root / "overlays" / "staging"
        self.production_dir = self.k8s_root / "overlays" / "production"
        self.production_operationalization_service = production_operationalization_service or ProductionOperationalizationService()
        self.supervision_command_service = supervision_command_service or ProductionSupervisionCommandService()

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
            "staging_kustomization": self.staging_dir / "kustomization.yaml",
            "staging_patch": STAGING_PATCH,
            "production_kustomization": self.production_dir / "kustomization.yaml",
            "production_patch": PRODUCTION_PATCH,
        }

    def _manifest_inventory(self) -> Dict[str, List[str]]:
        entries = self._manifest_paths()
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
        ]
        overlay_files = [
            "k8s/overlays/staging/kustomization.yaml",
            "k8s/overlays/staging/patches/staging-safety-patch.yaml",
            "k8s/overlays/production/kustomization.yaml",
            "k8s/overlays/production/patches/production-safety-patch.yaml",
        ]
        existing_base = [path for path in base_files if (self.k8s_root / path.replace("k8s/", "")).exists()]
        existing_overlay = [path for path in overlay_files if (self.k8s_root / path.replace("k8s/", "")).exists()]
        return {"base_files": existing_base, "overlay_files": existing_overlay}

    def _safety_model(self) -> Dict[str, Any]:
        base_config = _load_text(self.base_dir / "configmap.yaml")
        staging_patch = _load_text(self.staging_dir / "patches" / "staging-safety-patch.yaml")
        production_patch = _load_text(self.production_dir / "patches" / "production-safety-patch.yaml")
        all_text = "\n".join(
            _load_text(path)
            for path in self.k8s_root.rglob("*")
            if path.is_file() and path.suffix.lower() in {".yaml", ".yml", ".md"}
        )
        final_automation_disabled = 'LMCP_ALLOW_FINAL_AUTOMATION: "false"' in production_patch
        dry_run_mode_enabled = 'LMCP_DRY_RUN_MODE: "true"' in production_patch
        human_supervision_required = 'LMCP_REQUIRE_HUMAN_SUPERVISION: "true"' in production_patch
        submission_lock_required = "LMCP_SUBMISSION_LOCK_FILE:" in production_patch and "/app/runtime/production/go_live_guards/submission_locks.json" in production_patch
        production_overlay_separated_from_staging = "LMCP_ENV: staging" in staging_patch and "LMCP_ENV: production" in production_patch and "distributed-staging" in staging_patch and "distributed-production" in production_patch
        embedded_credentials_found = any(marker in all_text for marker in ["BEGIN PRIVATE KEY", "real-password", "prod-password", "password123", "AKIA", "ghp_", "sk-", "xoxb-"])
        return {
            "final_automation_disabled": final_automation_disabled,
            "dry_run_mode_enabled": dry_run_mode_enabled,
            "human_supervision_required": human_supervision_required,
            "submission_lock_required": submission_lock_required,
            "production_overlay_separated_from_staging": production_overlay_separated_from_staging,
            "embedded_credentials_found": embedded_credentials_found,
            "staging_mode_declared": "LMCP_ENV: staging" in staging_patch or "LMCP_ENV: staging" in base_config,
            "production_mode_declared": "LMCP_ENV: production" in production_patch,
        }

    def _manifest_ready(self, path: Path) -> bool:
        return path.exists() and path.is_file()

    def _production_sections(self) -> Dict[str, Dict[str, Any]]:
        payload = _safe_dict(self.production_operationalization_service.latest_production_governance())
        return {
            "operationalization": payload,
            "high_availability": _safe_dict(payload.get("high_availability_governance")),
            "backup_restore": _safe_dict(payload.get("backup_restore_governance")),
            "disaster_recovery": _safe_dict(payload.get("disaster_recovery_governance")),
            "operator_access": _safe_dict(payload.get("operator_access_governance")),
            "deployment_risk": _safe_dict(payload.get("deployment_risk_indicators")),
            "ha_readiness": _safe_dict(payload.get("ha_readiness_indicators")),
            "recovery_readiness": _safe_dict(payload.get("recovery_readiness_indicators")),
        }

    def _topology_snapshot(self) -> Dict[str, Any]:
        manifests = self._manifest_paths()
        sections = self._production_sections()
        supervision = _safe_dict(self.supervision_command_service.latest_supervision_command())
        operationalization = sections["operationalization"]
        high_availability = sections["high_availability"]
        backup_restore = sections["backup_restore"]
        disaster_recovery = sections["disaster_recovery"]
        operator_access = sections["operator_access"]
        deployment_risk = sections["deployment_risk"]
        ha_readiness = sections["ha_readiness"]
        recovery_readiness = sections["recovery_readiness"]
        safety_model = self._safety_model()
        manifest_inventory = self._manifest_inventory()
        runtime_controls = {
            "dry_run_enabled": safety_model["dry_run_mode_enabled"],
            "supervision_mandatory": safety_model["human_supervision_required"],
            "submission_lock_required": safety_model["submission_lock_required"],
            "live_authority": "NO" if not safety_model["final_automation_disabled"] else "WATCH",
        }
        redis_ready = self._manifest_ready(manifests["redis_deployment"]) and self._manifest_ready(manifests["redis_service"]) and _extract_replicas(_load_text(manifests["redis_deployment"])) >= 2
        postgres_ready = self._manifest_ready(manifests["postgres_statefulset"]) and self._manifest_ready(manifests["postgres_service"]) and self._manifest_ready(manifests["pvc"]) and _extract_replicas(_load_text(manifests["postgres_statefulset"])) >= 2
        quorum_ready = self._manifest_ready(manifests["network_policy"]) and _truthy(runtime_controls["dry_run_enabled"]) and _truthy(runtime_controls["supervision_mandatory"]) and not _truthy(deployment_risk.get("deployment_risk"))
        failover_ready = _truthy(_safe_dict(disaster_recovery.get("recovery_readiness_indicators")).get("final_readiness_cleared")) and _truthy(high_availability.get("high_availability_governance_status") == "ok")
        persistence_ready = self._manifest_ready(manifests["pvc"]) and _truthy(_safe_dict(backup_restore.get("recovery_readiness_indicators")).get("evidence_pack_available")) and _truthy(_safe_dict(backup_restore.get("recovery_readiness_indicators")).get("readiness_threshold_met"))
        replica_supervision_ready = _truthy(_safe_dict(supervision.get("supervision_coverage")).get("active_supervision_coverage_ready", True)) and _truthy(_safe_dict(operator_access.get("operator_access_risk_indicators")).get("pending_approval_backlog") is False)
        split_brain_ready = _truthy(self._manifest_ready(manifests["network_policy"])) and quorum_ready and _truthy(high_availability.get("high_availability_governance_status") == "ok")
        readiness_map = {
            "redis_ha_readiness": redis_ready,
            "postgres_replication_readiness": postgres_ready,
            "quorum_readiness": quorum_ready,
            "failover_orchestration_readiness": failover_ready,
            "persistence_durability_readiness": persistence_ready,
            "replica_supervision_readiness": replica_supervision_ready,
            "split_brain_prevention_readiness": split_brain_ready,
        }
        score = round(mean([100.0 if value else 0.0 for value in readiness_map.values()] or [0.0]), 2)
        blockers = []
        if safety_model["embedded_credentials_found"]:
            blockers.append("embedded credentials detected in k8s package")
        if not safety_model["production_overlay_separated_from_staging"]:
            blockers.append("production overlay is not separated from staging")
        if not safety_model["dry_run_mode_enabled"]:
            blockers.append("production overlay must keep dry-run enabled")
        if not safety_model["human_supervision_required"]:
            blockers.append("human supervision must remain mandatory")
        if not safety_model["submission_lock_required"]:
            blockers.append("submission lock enforcement is missing")
        missing_files = [name for name, path in manifests.items() if not self._manifest_ready(path)]
        if missing_files:
            blockers.append(f"missing manifest files: {', '.join(sorted(missing_files))}")

        warnings = []
        if not redis_ready:
            warnings.append("Redis HA readiness is not yet complete.")
        if not postgres_ready:
            warnings.append("PostgreSQL replication readiness is not yet complete.")
        if not quorum_ready:
            warnings.append("Quorum readiness is not yet complete.")
        if not failover_ready:
            warnings.append("Failover orchestration readiness is not yet complete.")
        if not persistence_ready:
            warnings.append("Persistence durability readiness is not yet complete.")
        if not replica_supervision_ready:
            warnings.append("Replica supervision readiness is not yet complete.")
        if not split_brain_ready:
            warnings.append("Split-brain prevention readiness is not yet complete.")
        if not _truthy(high_availability.get("high_availability_governance_status") == "ok"):
            warnings.append("Current production high-availability governance is not fully recovered.")

        if blockers:
            status = "blocked"
        elif score >= 85.0:
            status = "ok"
        else:
            status = "watch"

        authority = _authority_from_status(status)
        grade = "ready" if status == "ok" else "watch" if status == "watch" else "blocked"
        degradation_indicators = {key.replace("_readiness", "_degradation"): not value for key, value in readiness_map.items()}
        degradation_indicators["split_brain_risk"] = not split_brain_ready
        history_source = _safe_list(operationalization.get("production_governance_history"))
        if not history_source:
            history_source = [{"analysis_id": _safe_str(operationalization.get("analysis_id"), "ha-topology"), "generated_at": _safe_str(operationalization.get("generated_at"), _now_iso()), "production_readiness_score": score}]
        history: List[Dict[str, Any]] = []
        for item in history_source:
            item_score = _safe_float(item.get("production_readiness_score"), score)
            item_status = _safe_str(item.get("production_readiness_status"), status)
            item_authority = _authority_from_status(item_status)
            history.append(
                {
                    "analysis_id": _safe_str(item.get("analysis_id"), "ha-topology"),
                    "generated_at": _safe_str(item.get("generated_at"), _now_iso()),
                    "ha_topology_status": item_status,
                    "ha_topology_authority": item_authority,
                    "ha_topology_score": round(item_score if item_score else score, 2),
                    "ha_topology_grade": "ready" if item_status == "ok" else "watch" if item_status == "watch" else "blocked",
                    "redis_ha_readiness": {"ready": redis_ready, "status": "PASS" if redis_ready else "WARN", "score": 100.0 if redis_ready else 0.0},
                    "postgres_replication_readiness": {"ready": postgres_ready, "status": "PASS" if postgres_ready else "WARN", "score": 100.0 if postgres_ready else 0.0},
                    "quorum_readiness": {"ready": quorum_ready, "status": "PASS" if quorum_ready else "WARN", "score": 100.0 if quorum_ready else 0.0},
                    "failover_orchestration_readiness": {"ready": failover_ready, "status": "PASS" if failover_ready else "WARN", "score": 100.0 if failover_ready else 0.0},
                    "persistence_durability_readiness": {"ready": persistence_ready, "status": "PASS" if persistence_ready else "WARN", "score": 100.0 if persistence_ready else 0.0},
                    "replica_supervision_readiness": {"ready": replica_supervision_ready, "status": "PASS" if replica_supervision_ready else "WARN", "score": 100.0 if replica_supervision_ready else 0.0},
                    "split_brain_prevention_readiness": {"ready": split_brain_ready, "status": "PASS" if split_brain_ready else "WARN", "score": 100.0 if split_brain_ready else 0.0},
                    "ha_degradation_indicators": degradation_indicators,
                }
            )

        history_scores = [float(item.get("ha_topology_score", 0.0)) for item in history] or [score]
        history_summary = {
            "analysis_count": len(history),
            "latest_analysis_id": _safe_str(history[0].get("analysis_id"), "ha-topology") if history else "ha-topology",
            "latest_score": score,
            "score_history": _history_points(history_scores),
        }
        return {
            "analysis_id": f"{_safe_str(operationalization.get('analysis_id'), 'ha-topology')}:ha-topology",
            "generated_at": _safe_str(operationalization.get("generated_at"), _now_iso()),
            "status": status,
            "ha_topology_status": status,
            "ha_topology_authority": authority,
            "ha_topology_score": score,
            "ha_topology_grade": grade,
            "redis_ha_readiness": {"ready": redis_ready, "status": "PASS" if redis_ready else "WARN", "score": 100.0 if redis_ready else 0.0, "replicas": _extract_replicas(_load_text(manifests["redis_deployment"]))},
            "postgres_replication_readiness": {"ready": postgres_ready, "status": "PASS" if postgres_ready else "WARN", "score": 100.0 if postgres_ready else 0.0, "replicas": _extract_replicas(_load_text(manifests["postgres_statefulset"]))},
            "quorum_readiness": {"ready": quorum_ready, "status": "PASS" if quorum_ready else "WARN", "score": 100.0 if quorum_ready else 0.0},
            "failover_orchestration_readiness": {"ready": failover_ready, "status": "PASS" if failover_ready else "WARN", "score": 100.0 if failover_ready else 0.0},
            "persistence_durability_readiness": {"ready": persistence_ready, "status": "PASS" if persistence_ready else "WARN", "score": 100.0 if persistence_ready else 0.0},
            "replica_supervision_readiness": {"ready": replica_supervision_ready, "status": "PASS" if replica_supervision_ready else "WARN", "score": 100.0 if replica_supervision_ready else 0.0},
            "split_brain_prevention_readiness": {"ready": split_brain_ready, "status": "PASS" if split_brain_ready else "WARN", "score": 100.0 if split_brain_ready else 0.0},
            "ha_degradation_indicators": degradation_indicators,
            "manifest_inventory": manifest_inventory,
            "safety_model": safety_model,
            "runtime_controls": runtime_controls,
            "topology_sources": {
                "high_availability_governance": high_availability,
                "backup_restore_governance": backup_restore,
                "disaster_recovery_governance": disaster_recovery,
                "operator_access_governance": operator_access,
                "deployment_risk_indicators": deployment_risk,
                "ha_readiness_indicators": ha_readiness,
                "recovery_readiness_indicators": recovery_readiness,
            },
            "warnings": warnings,
            "unresolved_blockers": blockers,
            "ha_governance_history": history,
            "ha_topology_history": history,
            "ha_topology_history_summary": history_summary,
            "summary_counts": {
                "PASS": len([value for value in readiness_map.values() if value]),
                "WARN": len([value for value in readiness_map.values() if not value]) if status != "blocked" else 0,
                "FAIL": len(blockers),
            },
            "latest_ha_topology": {
                "analysis_id": f"{_safe_str(operationalization.get('analysis_id'), 'ha-topology')}:ha-topology",
                "generated_at": _safe_str(operationalization.get("generated_at"), _now_iso()),
                "status": status,
                "ha_topology_status": status,
                "ha_topology_authority": authority,
                "ha_topology_score": score,
                "ha_topology_grade": grade,
                "redis_ha_readiness": {"ready": redis_ready, "status": "PASS" if redis_ready else "WARN", "score": 100.0 if redis_ready else 0.0},
                "postgres_replication_readiness": {"ready": postgres_ready, "status": "PASS" if postgres_ready else "WARN", "score": 100.0 if postgres_ready else 0.0},
                "quorum_readiness": {"ready": quorum_ready, "status": "PASS" if quorum_ready else "WARN", "score": 100.0 if quorum_ready else 0.0},
                "failover_orchestration_readiness": {"ready": failover_ready, "status": "PASS" if failover_ready else "WARN", "score": 100.0 if failover_ready else 0.0},
                "persistence_durability_readiness": {"ready": persistence_ready, "status": "PASS" if persistence_ready else "WARN", "score": 100.0 if persistence_ready else 0.0},
                "replica_supervision_readiness": {"ready": replica_supervision_ready, "status": "PASS" if replica_supervision_ready else "WARN", "score": 100.0 if replica_supervision_ready else 0.0},
                "split_brain_prevention_readiness": {"ready": split_brain_ready, "status": "PASS" if split_brain_ready else "WARN", "score": 100.0 if split_brain_ready else 0.0},
                "ha_degradation_indicators": degradation_indicators,
                "manifest_inventory": manifest_inventory,
                "safety_model": safety_model,
                "runtime_controls": runtime_controls,
                "topology_sources": {
                    "high_availability_governance": high_availability,
                    "backup_restore_governance": backup_restore,
                    "disaster_recovery_governance": disaster_recovery,
                    "operator_access_governance": operator_access,
                    "deployment_risk_indicators": deployment_risk,
                    "ha_readiness_indicators": ha_readiness,
                    "recovery_readiness_indicators": recovery_readiness,
                },
            },
        }

    def list_ha_topology(self, limit: int = 20) -> Dict[str, Any]:
        latest = self._topology_snapshot()
        history = _safe_list(latest.get("ha_topology_history"))[: max(1, int(limit))]
        return {
            "status": latest["status"],
            "ha_topology_status": latest["ha_topology_status"],
            "ha_topology_authority": latest["ha_topology_authority"],
            "ha_topology_score": latest["ha_topology_score"],
            "ha_topology_grade": latest["ha_topology_grade"],
            **latest,
            "latest_ha_topology": latest["latest_ha_topology"],
            "ha_topology_history": history,
            "ha_topology_history_summary": latest["ha_topology_history_summary"],
            "summary_counts": latest["summary_counts"],
            "warnings": latest["warnings"],
        }

    def latest_ha_topology(self) -> Dict[str, Any]:
        return self.list_ha_topology(limit=1)

    def ha_topology_history(self, limit: int = 20) -> Dict[str, Any]:
        latest = self.list_ha_topology(limit=limit)
        history = latest["ha_topology_history"]
        return {
            "status": latest["status"],
            "ha_topology_status": latest["ha_topology_status"],
            "ha_topology_authority": latest["ha_topology_authority"],
            "ha_topology_score": latest["ha_topology_score"],
            "ha_topology_grade": latest["ha_topology_grade"],
            "count": len(history),
            "ha_topology_history": history,
            "ha_topology_history_summary": latest["ha_topology_history_summary"],
            "summary_counts": latest["summary_counts"],
            "warnings": latest["warnings"],
        }
