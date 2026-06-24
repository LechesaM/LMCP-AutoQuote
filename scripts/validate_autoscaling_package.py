#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


sys.dont_write_bytecode = True

ROOT_DIR = Path(__file__).resolve().parents[1]
K8S_ROOT = ROOT_DIR / "k8s"
BASE_DIR = K8S_ROOT / "base"
STAGING_DIR = K8S_ROOT / "overlays" / "staging"
PRODUCTION_DIR = K8S_ROOT / "overlays" / "production"
STAGING_PATCH = STAGING_DIR / "patches" / "staging-safety-patch.yaml"
PRODUCTION_PATCH = PRODUCTION_DIR / "patches" / "production-safety-patch.yaml"

REQUIRED_DIRECTORIES = [K8S_ROOT, BASE_DIR, STAGING_DIR, PRODUCTION_DIR]
REQUIRED_BASE_FILES = [
    BASE_DIR / "kustomization.yaml",
    BASE_DIR / "namespace.yaml",
    BASE_DIR / "configmap.yaml",
    BASE_DIR / "secret-placeholders.yaml",
    BASE_DIR / "backend-deployment.yaml",
    BASE_DIR / "backend-service.yaml",
    BASE_DIR / "frontend-deployment.yaml",
    BASE_DIR / "frontend-service.yaml",
    BASE_DIR / "worker-deployment.yaml",
    BASE_DIR / "redis-deployment.yaml",
    BASE_DIR / "redis-service.yaml",
    BASE_DIR / "postgres-statefulset.yaml",
    BASE_DIR / "postgres-service.yaml",
    BASE_DIR / "prometheus-deployment.yaml",
    BASE_DIR / "prometheus-service.yaml",
    BASE_DIR / "grafana-deployment.yaml",
    BASE_DIR / "grafana-service.yaml",
    BASE_DIR / "network-policy.yaml",
    BASE_DIR / "persistent-volume-claims.yaml",
    BASE_DIR / "tenant-namespace-template.yaml",
    BASE_DIR / "tenant-network-policy-template.yaml",
    BASE_DIR / "tenant-rbac-placeholder.yaml",
    BASE_DIR / "tenant-resource-quota-placeholder.yaml",
    BASE_DIR / "backend-hpa-placeholder.yaml",
    BASE_DIR / "frontend-hpa-placeholder.yaml",
    BASE_DIR / "worker-hpa-placeholder.yaml",
    BASE_DIR / "resource-quota-placeholder.yaml",
    BASE_DIR / "limit-range-placeholder.yaml",
    BASE_DIR / "queue-depth-scaling-placeholder.yaml",
]
REQUIRED_OVERLAY_FILES = [
    STAGING_PATCH,
    PRODUCTION_PATCH,
]
FORBIDDEN_MARKERS = [
    "BEGIN PRIVATE KEY",
    "-----BEGIN",
    "AKIA",
    "ghp_",
    "sk-",
    "xoxb-",
    "oauth_token=",
    "auth_token=",
    "real-secret",
    "real-password",
    "prod-password",
    "password123",
]


@dataclass
class CheckResult:
    level: str
    name: str
    message: str
    remediation: str = ""


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _contains_all(text: str, needles: Iterable[str]) -> bool:
    return all(needle in text for needle in needles)


def _check(condition: bool, name: str, pass_message: str, fail_message: str, remediation: str = "") -> CheckResult:
    return CheckResult("PASS", name, pass_message) if condition else CheckResult("FAIL", name, fail_message, remediation)


def _load_all_text(root_dir: Path) -> str:
    parts: List[str] = []
    for path in root_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".yaml", ".yml", ".md"}:
            try:
                parts.append(path.read_text(encoding="utf-8"))
            except Exception:
                continue
    return "\n".join(parts)


def build_autoscaling_package_validation_report(root_dir: Optional[Path] = None) -> Dict[str, Any]:
    root_dir = root_dir or ROOT_DIR
    k8s_root = root_dir / "k8s"
    base_dir = k8s_root / "base"
    staging_dir = k8s_root / "overlays" / "staging"
    production_dir = k8s_root / "overlays" / "production"

    backend_deployment = base_dir / "backend-deployment.yaml"
    frontend_deployment = base_dir / "frontend-deployment.yaml"
    worker_deployment = base_dir / "worker-deployment.yaml"
    backend_hpa = base_dir / "backend-hpa-placeholder.yaml"
    frontend_hpa = base_dir / "frontend-hpa-placeholder.yaml"
    worker_hpa = base_dir / "worker-hpa-placeholder.yaml"
    resource_quota = base_dir / "resource-quota-placeholder.yaml"
    limit_range = base_dir / "limit-range-placeholder.yaml"
    queue_depth_scaling = base_dir / "queue-depth-scaling-placeholder.yaml"
    tenant_namespace = base_dir / "tenant-namespace-template.yaml"
    tenant_network = base_dir / "tenant-network-policy-template.yaml"
    tenant_rbac = base_dir / "tenant-rbac-placeholder.yaml"
    tenant_quota = base_dir / "tenant-resource-quota-placeholder.yaml"
    alertmanager = base_dir / "alertmanager-placeholder.yaml"

    production_text = _text(PRODUCTION_PATCH)
    staging_text = _text(STAGING_PATCH)
    backend_text = _text(backend_deployment)
    frontend_text = _text(frontend_deployment)
    worker_text = _text(worker_deployment)
    all_text = _load_all_text(k8s_root)
    alert_text = _text(alertmanager)

    checks: List[CheckResult] = []
    checks.append(_check(all(path.exists() for path in REQUIRED_DIRECTORIES), "required manifest directories exist", "k8s package directories are present", "one or more required k8s package directories are missing", "Create k8s/base/, k8s/overlays/staging/, and k8s/overlays/production/."))
    checks.append(_check(all(path.exists() for path in REQUIRED_BASE_FILES), "required workload manifests exist", "all required base workload manifests are present", "one or more required base manifests are missing", "Keep the autoscaling placeholders, quotas, and limit ranges in k8s/base/."))
    checks.append(_check(all(path.exists() for path in REQUIRED_OVERLAY_FILES), "overlay manifests exist", "staging and production overlays are present", "one or more overlay manifests are missing", "Create the staging and production overlay safety patches."))

    required_controls = (
        'LMCP_ALLOW_FINAL_AUTOMATION: "false"',
        'LMCP_DRY_RUN_MODE: "true"',
        'LMCP_REQUIRE_HUMAN_SUPERVISION: "true"',
        'LMCP_SUBMISSION_LOCK_FILE:',
    )

    resource_requests_limits_present = all(
        [
            _contains_all(backend_text, ["resources:", "requests:", "limits:", "cpu:", "memory:"]),
            _contains_all(frontend_text, ["resources:", "requests:", "limits:", "cpu:", "memory:"]),
            _contains_all(worker_text, ["resources:", "requests:", "limits:", "cpu:", "memory:"]),
        ]
    )
    namespace_resource_quotas_present = resource_quota.exists() and _contains_all(_text(resource_quota), ["resource-quota-placeholder", "requests.cpu", "requests.memory", "limits.cpu", "limits.memory"])
    limit_ranges_present = limit_range.exists() and _contains_all(_text(limit_range), ["limit-range-placeholder", "defaultRequest", "default", "requests.cpu", "requests.memory", "limits.cpu", "limits.memory"])
    hpa_placeholders_present = all(
        [
            backend_hpa.exists() and _contains_all(_text(backend_hpa), ["backend-hpa-placeholder", "kind: HorizontalPodAutoscaler", "minReplicas:", "maxReplicas:", "name: backend"]),
            frontend_hpa.exists() and _contains_all(_text(frontend_hpa), ["frontend-hpa-placeholder", "kind: HorizontalPodAutoscaler", "minReplicas:", "maxReplicas:", "name: frontend"]),
            worker_hpa.exists() and _contains_all(_text(worker_hpa), ["worker-hpa-placeholder", "kind: HorizontalPodAutoscaler", "minReplicas:", "maxReplicas:", "name: worker"]),
        ]
    )
    queue_depth_scaling_present = queue_depth_scaling.exists() and _contains_all(_text(queue_depth_scaling), ["queue-depth-scaling-placeholder", "queue_depth_metric", "scale_up_threshold", "scale_down_threshold"])
    tenant_aware_scaling_boundaries_present = all(
        [
            tenant_namespace.exists() and _contains_all(_text(tenant_namespace), ["tenant-namespace-template-placeholder", 'lmcp.io/tenant-segregation: "enabled"', 'lmcp.io/tenant-onboarding: "disabled"']),
            tenant_network.exists() and _contains_all(_text(tenant_network), ["tenant-network-policy-template-placeholder", "policyTypes"]),
            tenant_rbac.exists() and _contains_all(_text(tenant_rbac), ["tenant-rbac-placeholder", "verbs:"]),
            tenant_quota.exists() and _contains_all(_text(tenant_quota), ["tenant-resource-quota-placeholder", "requests.cpu"]),
        ]
    )
    external_alert_delivery_disabled = alertmanager.exists() and not any(
        marker in alert_text.lower() for marker in ["webhook_configs", "email_configs", "slack", "pagerduty", "opsgenie", "victorops", "pushover", "telegram_configs"]
    )

    checks.append(_check(hpa_placeholders_present, "HPA placeholders exist", "backend, frontend, and worker HPA placeholders are present", "one or more HPA placeholders are missing", "Keep backend, frontend, and worker HPA placeholders in the base package."))
    checks.append(_check(resource_requests_limits_present, "resource requests/limits are represented", "backend, frontend, and worker resource requests and limits are represented", "resource requests/limits are missing from one or more deployments", "Keep resource requests and limits on the backend, frontend, and worker deployments."))
    checks.append(_check(namespace_resource_quotas_present, "namespace resource quotas are represented", "resource quota placeholders are present", "resource quota placeholder is missing", "Keep namespace quota placeholders in the base package."))
    checks.append(_check(limit_ranges_present, "limit ranges are represented", "limit range placeholders are present", "limit range placeholder is missing", "Keep limit range placeholders in the base package."))
    checks.append(_check(queue_depth_scaling_present, "queue-depth scaling is represented", "queue-depth scaling placeholder is present", "queue-depth scaling placeholder is missing", "Keep the queue-depth scaling placeholder in the base package."))
    checks.append(_check(tenant_aware_scaling_boundaries_present, "tenant-aware scaling boundaries are represented", "tenant isolation and workload boundary placeholders are present", "tenant-aware scaling boundaries are missing", "Keep tenant namespace, network policy, RBAC, and quota placeholders in the base package."))
    checks.append(_check(_contains_all(production_text, required_controls), "dry-run remains enforced", "production overlay keeps final automation disabled, dry-run enabled, and supervision required", "production safety controls are incomplete", "Keep final automation disabled, dry-run enabled, and human supervision required in the production overlay."))
    checks.append(_check("LMCP_ALLOW_FINAL_AUTOMATION: \"true\"" not in all_text, "no autonomous production authority is introduced", "no autonomous production authority was detected", "autonomous production authority was detected", "Keep LMCP_ALLOW_FINAL_AUTOMATION set to false across the package."))
    checks.append(_check('LMCP_REQUIRE_HUMAN_SUPERVISION: "true"' in production_text, "supervision remains mandatory", "human supervision remains mandatory in the production overlay", "human supervision is not mandatory in the production overlay", "Keep LMCP_REQUIRE_HUMAN_SUPERVISION set to true in production."))
    checks.append(_check(not any(marker in all_text for marker in FORBIDDEN_MARKERS), "no embedded credentials", "no embedded credentials were detected", "embedded credentials or secrets were detected in the package", "Keep only placeholder secrets and no production credentials in the package."))
    checks.append(_check("LMCP_ENV: staging" in staging_text and "LMCP_ENV: production" in production_text, "production overlay separated from staging", "staging and production overlays declare distinct environments", "staging and production overlays are not clearly separated", "Keep staging and production overlays separated by their own patch files and environment values."))
    checks.append(_check(external_alert_delivery_disabled, "external alert delivery remains disabled", "Alertmanager placeholder does not configure external delivery", "external alert delivery markers were detected", "Keep the alertmanager placeholder free of external delivery integrations."))

    summary_counts = {
        "PASS": len([check for check in checks if check.level == "PASS"]),
        "WARN": 0,
        "FAIL": len([check for check in checks if check.level == "FAIL"]),
    }
    overall_status = "PASS" if summary_counts["FAIL"] == 0 else "FAIL"
    safety_model = {
        "hpa_placeholders_present": hpa_placeholders_present,
        "resource_requests_limits_present": resource_requests_limits_present,
        "namespace_resource_quotas_present": namespace_resource_quotas_present,
        "limit_ranges_present": limit_ranges_present,
        "queue_depth_scaling_present": queue_depth_scaling_present,
        "tenant_aware_scaling_boundaries_present": tenant_aware_scaling_boundaries_present,
        "no_autonomous_production_authority": "LMCP_ALLOW_FINAL_AUTOMATION: \"true\"" not in all_text and "LMCP_ALLOW_FINAL_AUTOMATION: \"false\"" in production_text,
        "dry_run_mode_enabled": "LMCP_DRY_RUN_MODE: \"true\"" in production_text,
        "human_supervision_required": "LMCP_REQUIRE_HUMAN_SUPERVISION: \"true\"" in production_text,
        "external_alert_delivery_disabled": external_alert_delivery_disabled,
        "embedded_credentials_found": any(marker in all_text for marker in FORBIDDEN_MARKERS),
        "production_overlay_separated_from_staging": "LMCP_ENV: staging" in staging_text and "LMCP_ENV: production" in production_text,
    }
    manifest_inventory = {
        "base_files": [path.name for path in REQUIRED_BASE_FILES if path.exists()],
        "overlay_files": [path.name for path in REQUIRED_OVERLAY_FILES if path.exists()],
    }
    return {
        "overall_status": overall_status,
        "summary_counts": summary_counts,
        "checks": [check.__dict__ for check in checks],
        "safety_model": safety_model,
        "manifest_inventory": manifest_inventory,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the autoscaling governance package.")
    parser.add_argument("--root-dir", default=str(ROOT_DIR), help="Repository root to validate.")
    args = parser.parse_args(argv)
    report = build_autoscaling_package_validation_report(root_dir=Path(args.root_dir))
    print(f"Autoscaling package validation: {report['overall_status']}")
    for check in report["checks"]:
        print(f"[{check['level']}] {check['name']}: {check['message']}")
        if check["level"] == "FAIL" and check["remediation"]:
            print(f"  remediation: {check['remediation']}")
    return 0 if report["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
