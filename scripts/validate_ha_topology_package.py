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
]
REQUIRED_OVERLAY_FILES = [
    STAGING_DIR / "kustomization.yaml",
    STAGING_PATCH,
    PRODUCTION_DIR / "kustomization.yaml",
    PRODUCTION_PATCH,
]
REQUIRED_OBSERVABILITY_FILES = [
    BASE_DIR / "prometheus-deployment.yaml",
    BASE_DIR / "prometheus-service.yaml",
    BASE_DIR / "grafana-deployment.yaml",
    BASE_DIR / "grafana-service.yaml",
]
REQUIRED_STORAGE_FILES = [BASE_DIR / "persistent-volume-claims.yaml"]
REQUIRED_NETWORK_POLICY_FILES = [BASE_DIR / "network-policy.yaml"]
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


def _check(condition: bool, name: str, pass_message: str, fail_message: str, remediation: str = "") -> CheckResult:
    if condition:
        return CheckResult("PASS", name, pass_message)
    return CheckResult("FAIL", name, fail_message, remediation)


def _contains_all(text: str, needles: Iterable[str]) -> bool:
    return all(needle in text for needle in needles)


def _file_exists(path: Path) -> bool:
    return path.exists() and path.is_file()


def _load_all_text(root_dir: Path) -> str:
    parts: List[str] = []
    for path in root_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".yaml", ".yml", ".md"}:
            try:
                parts.append(path.read_text(encoding="utf-8"))
            except Exception:
                continue
    return "\n".join(parts)


def build_ha_topology_package_validation_report(root_dir: Optional[Path] = None) -> Dict[str, Any]:
    root_dir = root_dir or ROOT_DIR
    k8s_root = root_dir / "k8s"
    base_dir = k8s_root / "base"
    staging_dir = k8s_root / "overlays" / "staging"
    production_dir = k8s_root / "overlays" / "production"
    staging_patch = staging_dir / "patches" / "staging-safety-patch.yaml"
    production_patch = production_dir / "patches" / "production-safety-patch.yaml"
    required_observability_files = [
        base_dir / "prometheus-deployment.yaml",
        base_dir / "prometheus-service.yaml",
        base_dir / "grafana-deployment.yaml",
        base_dir / "grafana-service.yaml",
    ]
    required_storage_files = [base_dir / "persistent-volume-claims.yaml"]
    required_network_policy_files = [base_dir / "network-policy.yaml"]

    checks: List[CheckResult] = []
    checks.append(
        _check(
            all(path.exists() for path in REQUIRED_DIRECTORIES),
            "required manifest directories exist",
            "k8s package directories are present",
            "one or more required k8s package directories are missing",
            "Create k8s/base/, k8s/overlays/staging/, and k8s/overlays/production/.",
        )
    )
    checks.append(
        _check(
            all(path.exists() for path in REQUIRED_BASE_FILES),
            "required workload manifests exist",
            "all required base workload manifests are present",
            "one or more required workload manifests are missing",
            "Keep backend, frontend, worker, Redis, PostgreSQL, Prometheus, and Grafana manifests in k8s/base/.",
        )
    )
    checks.append(
        _check(
            all(path.exists() for path in REQUIRED_OVERLAY_FILES),
            "overlay manifests exist",
            "staging and production overlays are present",
            "one or more overlay manifests are missing",
            "Create the staging and production overlay kustomization files and patches.",
        )
    )

    production_text = _text(production_patch)
    staging_text = _text(staging_patch)
    all_text = _load_all_text(k8s_root)
    required_controls = (
        'LMCP_ALLOW_FINAL_AUTOMATION: "false"',
        'LMCP_DRY_RUN_MODE: "true"',
        'LMCP_REQUIRE_HUMAN_SUPERVISION: "true"',
        'LMCP_SUBMISSION_LOCK_FILE:',
    )

    checks.append(
        _check(
            _contains_all(production_text, required_controls),
            "dry-run enforcement exists",
            "production overlay keeps final automation disabled, dry-run enabled, and supervision required",
            "production safety controls are incomplete",
            "Keep final automation disabled, dry-run enabled, and human supervision required in the production overlay.",
        )
    )
    checks.append(
        _check(
            "LMCP_ENV: staging" in staging_text and "LMCP_ENV: production" in production_text,
            "production overlay separated from staging",
            "staging and production overlays declare distinct environments",
            "staging and production overlays are not clearly separated",
            "Keep staging and production overlays separated by their own patch files and environment values.",
        )
    )
    checks.append(
        _check(
            not any(marker in all_text for marker in FORBIDDEN_MARKERS),
            "no embedded credentials",
            "no embedded credentials were detected",
            "embedded credentials or secrets were detected in the package",
            "Keep only placeholder secrets and no production credentials in the package.",
        )
    )
    checks.append(
        _check(
            _contains_all(production_text, required_controls),
            "final automation disabled",
            "final automation remains disabled in the production overlay",
            "final automation is not disabled in the production overlay",
            "Keep LMCP_ALLOW_FINAL_AUTOMATION set to false in production.",
        )
    )
    checks.append(
        _check(
            'LMCP_REQUIRE_HUMAN_SUPERVISION: "true"' in production_text,
            "supervision mandatory",
            "human supervision remains mandatory in the production overlay",
            "human supervision is not mandatory in the production overlay",
            "Keep LMCP_REQUIRE_HUMAN_SUPERVISION set to true in production.",
        )
    )
    checks.append(
        _check(
            all(path.exists() for path in required_observability_files),
            "observability manifests exist",
            "observability manifests are present",
            "observability manifests are missing",
            "Keep Prometheus and Grafana manifests in the base package.",
        )
    )
    checks.append(
        _check(
            all(path.exists() for path in required_storage_files),
            "storage placeholders exist",
            "storage placeholder manifests are present",
            "storage placeholder manifests are missing",
            "Keep persistent volume claim placeholders in the base package.",
        )
    )
    checks.append(
        _check(
            all(path.exists() for path in required_network_policy_files),
            "network policy placeholders exist",
            "network policy placeholder manifests are present",
            "network policy placeholder manifests are missing",
            "Keep network policy placeholders in the base package.",
        )
    )

    summary_counts = {
        "PASS": len([check for check in checks if check.level == "PASS"]),
        "WARN": 0,
        "FAIL": len([check for check in checks if check.level == "FAIL"]),
    }
    overall_status = "PASS" if summary_counts["FAIL"] == 0 else "FAIL"
    safety_model = {
        "final_automation_disabled": "LMCP_ALLOW_FINAL_AUTOMATION: \"false\"" in production_text,
        "dry_run_mode_enabled": "LMCP_DRY_RUN_MODE: \"true\"" in production_text,
        "human_supervision_required": "LMCP_REQUIRE_HUMAN_SUPERVISION: \"true\"" in production_text,
        "submission_lock_required": "LMCP_SUBMISSION_LOCK_FILE:" in production_text,
        "production_overlay_separated_from_staging": "LMCP_ENV: staging" in staging_text and "LMCP_ENV: production" in production_text,
        "embedded_credentials_found": any(marker in all_text for marker in FORBIDDEN_MARKERS),
    }
    base_inventory_paths = [
        root_dir / "k8s" / "base" / "backend-deployment.yaml",
        root_dir / "k8s" / "base" / "backend-service.yaml",
        root_dir / "k8s" / "base" / "frontend-deployment.yaml",
        root_dir / "k8s" / "base" / "frontend-service.yaml",
        root_dir / "k8s" / "base" / "worker-deployment.yaml",
        root_dir / "k8s" / "base" / "redis-deployment.yaml",
        root_dir / "k8s" / "base" / "redis-service.yaml",
        root_dir / "k8s" / "base" / "postgres-statefulset.yaml",
        root_dir / "k8s" / "base" / "postgres-service.yaml",
        root_dir / "k8s" / "base" / "prometheus-deployment.yaml",
        root_dir / "k8s" / "base" / "prometheus-service.yaml",
        root_dir / "k8s" / "base" / "grafana-deployment.yaml",
        root_dir / "k8s" / "base" / "grafana-service.yaml",
        root_dir / "k8s" / "base" / "network-policy.yaml",
        root_dir / "k8s" / "base" / "persistent-volume-claims.yaml",
        root_dir / "k8s" / "base" / "configmap.yaml",
        root_dir / "k8s" / "base" / "secret-placeholders.yaml",
    ]
    overlay_inventory_paths = [
        root_dir / "k8s" / "overlays" / "staging" / "kustomization.yaml",
        root_dir / "k8s" / "overlays" / "staging" / "patches" / "staging-safety-patch.yaml",
        root_dir / "k8s" / "overlays" / "production" / "kustomization.yaml",
        root_dir / "k8s" / "overlays" / "production" / "patches" / "production-safety-patch.yaml",
    ]
    manifest_inventory = {
        "base_files": [str(path.relative_to(root_dir)) for path in base_inventory_paths if _file_exists(path)],
        "overlay_files": [str(path.relative_to(root_dir)) for path in overlay_inventory_paths if _file_exists(path)],
    }

    return {
        "generated_at": "2026-06-24T00:00:00+00:00",
        "overall_status": overall_status,
        "summary_counts": summary_counts,
        "safety_model": safety_model,
        "manifest_inventory": manifest_inventory,
        "checks": [check.__dict__ for check in checks],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the HA topology Kubernetes package scaffold.")
    parser.add_argument("--root-dir", default=str(ROOT_DIR), help="Repository root to validate")
    args = parser.parse_args(argv)
    report = build_ha_topology_package_validation_report(root_dir=Path(args.root_dir))
    print(f"HA topology package validation: {report['overall_status']}")
    for check in report["checks"]:
        print(f"- {check['level']}: {check['name']} :: {check['message']}")
    return 0 if report["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
