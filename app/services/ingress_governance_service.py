from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.operational_exception_service import _safe_dict, _safe_float, _safe_int, _safe_list, _safe_str


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
        return value.strip().lower() in {"true", "1", "yes", "y", "ok", "ready", "enabled", "internal-only"}
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


class IngressGovernanceService:
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
            "ingress": self.base_dir / "ingress.yaml",
            "tls_secret_placeholder": self.base_dir / "tls-secret-placeholder.yaml",
            "cert_manager_placeholder": self.base_dir / "cert-manager-placeholder.yaml",
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
        ingress_text = self._text(self.base_dir / "ingress.yaml")
        cert_text = self._text(self.base_dir / "cert-manager-placeholder.yaml")
        tls_text = self._text(self.base_dir / "tls-secret-placeholder.yaml")
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
            "public_exposure_disabled": 'lmcp.io/public-exposure: "disabled"' in ingress_text,
            "internal_routing_enabled": 'lmcp.io/internal-routing: "enabled"' in ingress_text,
            "external_routing_disabled": 'lmcp.io/external-routing: "disabled"' in ingress_text,
            "admin_access_internal_only": 'lmcp.io/admin-access: "internal-only"' in ingress_text,
            "observability_access_internal_only": 'lmcp.io/observability-access: "internal-only"' in ingress_text,
            "internal_ingress_class": "ingressClassName: internal-placeholder" in ingress_text,
            "placeholder_host": "placeholder.lmcp.local" in ingress_text,
            "placeholder_secret": "tls-secret-placeholder" in ingress_text,
            "placeholder_certificate": "placeholder-issuer" in cert_text and "tls-secret-placeholder" in cert_text,
            "placeholder_tls_secret": "tls.crt:" in tls_text and "tls.key:" in tls_text,
            "embedded_credentials_found": any(
                marker in all_text for marker in ["BEGIN PRIVATE KEY", "AKIA", "ghp_", "sk-", "xoxb-", "real-password", "prod-password", "password123"]
            ),
            "live_dns_found": any(marker in ingress_text for marker in ["example.com", "letsencrypt", "public.example", "www.", "https://"]),
            "live_certificate_found": any(marker in cert_text.lower() for marker in ["letsencrypt", "cluster-issuer: letsencrypt", "example.com", "public.example"]),
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
            "k8s/base/ingress.yaml",
            "k8s/base/tls-secret-placeholder.yaml",
            "k8s/base/cert-manager-placeholder.yaml",
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
        return {
            "ready": ready,
            "status": "PASS" if ready else "WARN",
            "score": 100.0 if ready else 0.0,
            "evidence": evidence or {},
        }

    def _snapshot(self) -> Dict[str, Any]:
        paths = self._manifest_paths()
        safety = self._safety_model()
        inventory = self._manifest_inventory()

        missing_files = [name for name, path in paths.items() if not self._file_ready(path)]
        tls_ready = all(
            [
                self._file_ready(paths["ingress"]),
                self._file_ready(paths["tls_secret_placeholder"]),
                self._file_ready(paths["cert_manager_placeholder"]),
                safety["placeholder_secret"],
                safety["placeholder_certificate"],
                safety["placeholder_tls_secret"],
                not safety["live_certificate_found"],
                not safety["live_dns_found"],
            ]
        )
        ingress_isolation_ready = all(
            [
                safety["internal_ingress_class"],
                safety["public_exposure_disabled"],
                safety["internal_routing_enabled"],
                safety["external_routing_disabled"],
            ]
        )
        internal_external_routing_segregation_ready = safety["internal_routing_enabled"] and safety["external_routing_disabled"]
        certificate_governance_ready = all(
            [
                self._file_ready(paths["cert_manager_placeholder"]),
                safety["placeholder_certificate"],
                safety["placeholder_secret"],
                not safety["live_certificate_found"],
            ]
        )
        api_exposure_governance_ready = safety["placeholder_host"] and safety["public_exposure_disabled"] and safety["internal_ingress_class"]
        observability_ingress_governance_ready = safety["observability_access_internal_only"] and safety["public_exposure_disabled"]
        administrative_access_isolation_ready = safety["admin_access_internal_only"] and safety["public_exposure_disabled"]
        public_attack_surface_safe = not safety["live_dns_found"] and not safety["live_certificate_found"] and safety["public_exposure_disabled"]

        readiness_map = {
            "tls_readiness": tls_ready,
            "ingress_isolation_readiness": ingress_isolation_ready,
            "internal_external_routing_segregation_readiness": internal_external_routing_segregation_ready,
            "certificate_governance_readiness": certificate_governance_ready,
            "api_exposure_governance_readiness": api_exposure_governance_ready,
            "observability_ingress_governance_readiness": observability_ingress_governance_ready,
            "administrative_access_isolation_readiness": administrative_access_isolation_ready,
            "public_attack_surface_indicator": public_attack_surface_safe,
        }
        degradation_indicators = {key.replace("_readiness", "_degradation").replace("_indicator", "_degradation"): not value for key, value in readiness_map.items()}
        degradation_indicators["public_attack_surface_degradation"] = not public_attack_surface_safe

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
        if not safety["public_exposure_disabled"]:
            blockers.append("public exposure enablement is not allowed")
        if safety["live_dns_found"]:
            blockers.append("live DNS markers were detected in the ingress package")
        if safety["live_certificate_found"]:
            blockers.append("live certificate markers were detected in the ingress package")
        if safety["embedded_credentials_found"]:
            blockers.append("embedded credentials were detected in the ingress package")

        warnings = []
        if not tls_ready:
            warnings.append("TLS readiness is not yet complete.")
        if not ingress_isolation_ready:
            warnings.append("Ingress isolation readiness is not yet complete.")
        if not internal_external_routing_segregation_ready:
            warnings.append("Internal versus external routing segregation is not yet complete.")
        if not certificate_governance_ready:
            warnings.append("Certificate governance readiness is not yet complete.")
        if not api_exposure_governance_ready:
            warnings.append("API exposure governance is not yet complete.")
        if not observability_ingress_governance_ready:
            warnings.append("Observability ingress governance is not yet complete.")
        if not administrative_access_isolation_ready:
            warnings.append("Administrative access isolation is not yet complete.")
        if not public_attack_surface_safe:
            warnings.append("Public attack-surface indicators remain elevated.")

        blocker_sources = [
            {"source": "tls_readiness", "ready": tls_ready, "blockers": [] if tls_ready else ["TLS placeholder artifacts are incomplete"]},
            {"source": "ingress_isolation_readiness", "ready": ingress_isolation_ready, "blockers": [] if ingress_isolation_ready else ["Ingress isolation is not fully internal-only"]},
            {"source": "internal_external_routing_segregation_readiness", "ready": internal_external_routing_segregation_ready, "blockers": [] if internal_external_routing_segregation_ready else ["Internal and external routing are not segregated"]},
            {"source": "certificate_governance_readiness", "ready": certificate_governance_ready, "blockers": [] if certificate_governance_ready else ["Certificate governance is not fully placeholder-only"]},
            {"source": "api_exposure_governance_readiness", "ready": api_exposure_governance_ready, "blockers": [] if api_exposure_governance_ready else ["API exposure remains broader than the staged boundary"]},
            {"source": "observability_ingress_governance_readiness", "ready": observability_ingress_governance_ready, "blockers": [] if observability_ingress_governance_ready else ["Observability ingress is not internal-only"]},
            {"source": "administrative_access_isolation_readiness", "ready": administrative_access_isolation_ready, "blockers": [] if administrative_access_isolation_ready else ["Administrative access is not isolated to internal traffic"]},
            {"source": "public_attack_surface_indicator", "ready": public_attack_surface_safe, "blockers": [] if public_attack_surface_safe else ["Public attack-surface indicators remain active"]},
        ]

        component_scores = [100.0 if value else 0.0 for value in readiness_map.values()]
        base_score = round(mean(component_scores), 2) if component_scores else 0.0
        deduction = round((len(blockers) * 6.0) + (len(warnings) * 1.5), 2)
        score_after_deductions = max(0.0, round(base_score - deduction, 2))
        if blockers:
            recovery_state = "unresolved-blocked"
            ingress_score = min(score_after_deductions, 69.99)
        elif warnings or not all(readiness_map.values()):
            recovery_state = "degraded-but-recovering"
            ingress_score = min(max(score_after_deductions, 70.0), 84.99)
        else:
            recovery_state = "recovered"
            ingress_score = max(score_after_deductions, 90.0)
        ingress_score = round(min(ingress_score, 100.0), 2)

        status = _status_from_score(ingress_score)
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
                "analysis_id": "ingress-governance",
                "generated_at": _now_iso(),
                "recovery_state": recovery_state,
                "ingress_governance_status": status,
                "ingress_governance_authority": authority,
                "ingress_governance_score": ingress_score,
                "unresolved_blocker_count": len(blockers),
            }
        ]
        recovery_rationale = {
            "state": recovery_state,
            "summary": (
                "Ingress governance is fully recovered."
                if recovery_state == "recovered"
                else "Ingress governance is degraded but still progressing."
                if recovery_state == "degraded-but-recovering"
                else "Ingress governance remains blocked by unresolved safety issues."
            ),
            "score_impact": {
                "base_score": base_score,
                "deductions": deduction,
                "final_score": ingress_score,
            },
            "state_basis": {
                "tls_ready": tls_ready,
                "ingress_isolation_ready": ingress_isolation_ready,
                "internal_external_routing_segregation_ready": internal_external_routing_segregation_ready,
                "certificate_governance_ready": certificate_governance_ready,
                "api_exposure_governance_ready": api_exposure_governance_ready,
                "observability_ingress_governance_ready": observability_ingress_governance_ready,
                "administrative_access_isolation_ready": administrative_access_isolation_ready,
                "public_attack_surface_safe": public_attack_surface_safe,
                "unresolved_blocker_count": len(blockers),
            },
        }

        latest_ingress_governance = {
            "analysis_id": "ingress-governance:latest",
            "generated_at": _now_iso(),
            "status": status,
            "ingress_governance_status": status,
            "ingress_governance_authority": authority,
            "ingress_governance_score": ingress_score,
            "ingress_governance_grade": grade,
            "recovery_state": recovery_state,
            "recovery_state_history": recovery_state_history,
            "unresolved_blockers": blockers,
            "recovery_rationale": recovery_rationale,
            "blocker_sources": blocker_sources,
            "tls_readiness": self._component(tls_ready, {"placeholder_ingress": safety["placeholder_host"], "placeholder_secret": safety["placeholder_secret"]}),
            "ingress_isolation_readiness": self._component(ingress_isolation_ready, {"internal_ingress_class": safety["internal_ingress_class"]}),
            "internal_external_routing_segregation_readiness": self._component(internal_external_routing_segregation_ready),
            "certificate_governance_readiness": self._component(certificate_governance_ready, {"placeholder_certificate": safety["placeholder_certificate"]}),
            "api_exposure_governance_readiness": self._component(api_exposure_governance_ready),
            "observability_ingress_governance_readiness": self._component(observability_ingress_governance_ready),
            "administrative_access_isolation_readiness": self._component(administrative_access_isolation_ready),
            "public_attack_surface_indicators": {
                "public_exposure_disabled": safety["public_exposure_disabled"],
                "placeholder_host_only": safety["placeholder_host"],
                "live_dns_detected": safety["live_dns_found"],
                "live_certificate_detected": safety["live_certificate_found"],
                "attack_surface_safe": public_attack_surface_safe,
            },
            "ingress_degradation_indicators": degradation_indicators,
            "manifest_inventory": inventory,
            "safety_model": safety,
            "warnings": warnings,
        }
        latest_ingress_governance["ingress_governance_history"] = recovery_state_history
        return latest_ingress_governance

    def _history(self, limit: int = 20) -> List[Dict[str, Any]]:
        latest = self._snapshot()
        history = [
            {
                "analysis_id": latest["analysis_id"],
                "generated_at": latest["generated_at"],
                "ingress_governance_status": latest["ingress_governance_status"],
                "ingress_governance_authority": latest["ingress_governance_authority"],
                "ingress_governance_score": latest["ingress_governance_score"],
                "ingress_governance_grade": latest["ingress_governance_grade"],
                "recovery_state": latest["recovery_state"],
                "recovery_state_history": latest["recovery_state_history"],
                "unresolved_blockers": latest["unresolved_blockers"],
                "recovery_rationale": latest["recovery_rationale"],
                "blocker_sources": latest["blocker_sources"],
            }
        ]
        return history[: max(1, int(limit))]

    def list_ingress_governance(self, limit: int = 20) -> Dict[str, Any]:
        latest = self._snapshot()
        history = self._history(limit=limit)
        scores = [float(item.get("ingress_governance_score", 0.0)) for item in history] or [latest["ingress_governance_score"]]
        summary = {
            "analysis_count": len(history),
            "latest_analysis_id": _safe_str(history[0].get("analysis_id"), latest["analysis_id"]) if history else latest["analysis_id"],
            "latest_score": latest["ingress_governance_score"],
            "score_history": _history_points(scores),
            "recovery_state_history": [item.get("recovery_state_history", []) for item in history],
        }
        return {
            "status": latest["status"],
            "ingress_governance_status": latest["ingress_governance_status"],
            "ingress_governance_authority": latest["ingress_governance_authority"],
            "ingress_governance_score": latest["ingress_governance_score"],
            "ingress_governance_grade": latest["ingress_governance_grade"],
            **latest,
            "latest_ingress_governance": latest,
            "ingress_governance_history": history,
            "ingress_governance_history_summary": summary,
            "summary_counts": {
                "PASS": 1 if latest["recovery_state"] == "recovered" else 0,
                "WARN": 1 if latest["recovery_state"] == "degraded-but-recovering" else 0,
                "FAIL": 1 if latest["recovery_state"] == "unresolved-blocked" else 0,
            },
            "warnings": latest["warnings"],
        }

    def latest_ingress_governance(self) -> Dict[str, Any]:
        return self.list_ingress_governance(limit=1)

    def ingress_governance_history(self, limit: int = 20) -> Dict[str, Any]:
        latest = self.list_ingress_governance(limit=limit)
        history = latest["ingress_governance_history"]
        return {
            "status": latest["status"],
            "ingress_governance_status": latest["ingress_governance_status"],
            "ingress_governance_authority": latest["ingress_governance_authority"],
            "ingress_governance_score": latest["ingress_governance_score"],
            "ingress_governance_grade": latest["ingress_governance_grade"],
            "count": len(history),
            "ingress_governance_history": history,
            "ingress_governance_history_summary": latest["ingress_governance_history_summary"],
            "summary_counts": latest["summary_counts"],
            "warnings": latest["warnings"],
        }
