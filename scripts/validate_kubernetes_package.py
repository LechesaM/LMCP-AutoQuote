#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
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
    STAGING_DIR / "patches" / "staging-safety-patch.yaml",
    PRODUCTION_DIR / "kustomization.yaml",
    PRODUCTION_DIR / "patches" / "production-safety-patch.yaml",
]
REQUIRED_WORKLOAD_FILES = [
    BASE_DIR / "backend-deployment.yaml",
    BASE_DIR / "backend-service.yaml",
    BASE_DIR / "frontend-deployment.yaml",
    BASE_DIR / "frontend-service.yaml",
    BASE_DIR / "worker-deployment.yaml",
    BASE_DIR / "redis-deployment.yaml",
    BASE_DIR / "postgres-statefulset.yaml",
    BASE_DIR / "prometheus-deployment.yaml",
    BASE_DIR / "prometheus-service.yaml",
    BASE_DIR / "grafana-deployment.yaml",
    BASE_DIR / "grafana-service.yaml",
]
REQUIRED_STORAGE_FILES = [BASE_DIR / "persistent-volume-claims.yaml"]
REQUIRED_OBSERVABILITY_FILES = [
    BASE_DIR / "prometheus-deployment.yaml",
    BASE_DIR / "prometheus-service.yaml",
    BASE_DIR / "grafana-deployment.yaml",
    BASE_DIR / "grafana-service.yaml",
]
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


def _manifest_inventory(root_dir: Path) -> Dict[str, List[str]]:
    overlay_paths = [
        root_dir / "k8s" / "overlays" / "staging" / "kustomization.yaml",
        root_dir / "k8s" / "overlays" / "staging" / "patches" / "staging-safety-patch.yaml",
        root_dir / "k8s" / "overlays" / "production" / "kustomization.yaml",
        root_dir / "k8s" / "overlays" / "production" / "patches" / "production-safety-patch.yaml",
    ]
    return {
        "base_files": [str((root_dir / "k8s" / "base" / path.name).relative_to(root_dir)) for path in REQUIRED_BASE_FILES if _file_exists(root_dir / "k8s" / "base" / path.name)],
        "overlay_files": [str(path.relative_to(root_dir)) for path in overlay_paths if _file_exists(path)],
        "workload_files": [str((root_dir / "k8s" / "base" / path.name).relative_to(root_dir)) for path in REQUIRED_WORKLOAD_FILES if _file_exists(root_dir / "k8s" / "base" / path.name)],
    }


def build_kubernetes_package_validation_report(root_dir: Optional[Path] = None) -> Dict[str, Any]:
    root_dir = root_dir or ROOT_DIR
    k8s_root = root_dir / "k8s"
    base_dir = k8s_root / "base"
    staging_dir = k8s_root / "overlays" / "staging"
    production_dir = k8s_root / "overlays" / "production"

    required_base_files = [base_dir / path.name for path in REQUIRED_BASE_FILES]
    required_overlay_files = [
        staging_dir / "kustomization.yaml",
        staging_dir / "patches" / "staging-safety-patch.yaml",
        production_dir / "kustomization.yaml",
        production_dir / "patches" / "production-safety-patch.yaml",
    ]
    required_workload_files = [base_dir / path.name for path in REQUIRED_WORKLOAD_FILES]
    required_storage_files = [base_dir / path.name for path in REQUIRED_STORAGE_FILES]
    required_observability_files = [base_dir / path.name for path in REQUIRED_OBSERVABILITY_FILES]
    required_network_policy_files = [base_dir / path.name for path in REQUIRED_NETWORK_POLICY_FILES]

    checks: List[CheckResult] = []

    checks.append(
        _check(
            all(path.exists() for path in [k8s_root, base_dir, staging_dir, production_dir]),
            "required manifest directories exist",
            "k8s package directories are present",
            "one or more required k8s package directories are missing",
            "Create k8s/base/, k8s/overlays/staging/, and k8s/overlays/production/.",
        )
    )

    checks.append(
        _check(
            all(path.exists() for path in required_base_files),
            "required workload manifests exist",
            "all required base workload manifests are present",
            "one or more required workload manifests are missing",
            "Keep backend, frontend, worker, Redis, PostgreSQL, Prometheus, and Grafana manifests in k8s/base/.",
        )
    )

    checks.append(
        _check(
            all(path.exists() for path in required_overlay_files),
            "overlay manifests exist",
            "staging and production overlays are present",
            "one or more overlay manifests are missing",
            "Create the staging and production overlay kustomization files and patches.",
        )
    )

    base_config = _text(base_dir / "configmap.yaml")
    production_patch = _text(production_dir / "patches" / "production-safety-patch.yaml")
    staging_patch = _text(staging_dir / "patches" / "staging-safety-patch.yaml")
    all_text = _load_all_text(k8s_root)

    checks.append(
        _check(
            _contains_all(
                production_patch,
                (
                    'LMCP_ALLOW_FINAL_AUTOMATION: "false"',
                    'LMCP_DRY_RUN_MODE: "true"',
                    'LMCP_REQUIRE_HUMAN_SUPERVISION: "true"',
                    "LMCP_SUBMISSION_LOCK_FILE:",
                ),
            ),
            "dry-run enforcement exists",
            "production safety controls are incomplete",
            "Keep final automation disabled, dry-run enabled, and human supervision required in the production overlay.",
        )
    )

    checks.append(
        _check(
            _contains_all(
                production_patch,
                (
                    'LMCP_ALLOW_FINAL_AUTOMATION: "false"',
                    'LMCP_DRY_RUN_MODE: "true"',
                    'LMCP_REQUIRE_HUMAN_SUPERVISION: "true"',
                    "/app/runtime/production/go_live_guards/submission_locks.json",
                ),
            ),
            "production overlay safety values preserved",
            "production overlay safety values drifted from the locked defaults",
            "Keep the production overlay locked to supervised dry-run defaults and the production submission lock path.",
        )
    )

    checks.append(
        _check(
            _contains_all(
                staging_patch,
                (
                    'LMCP_ALLOW_FINAL_AUTOMATION: "false"',
                    'LMCP_DRY_RUN_MODE: "true"',
                    'LMCP_REQUIRE_HUMAN_SUPERVISION: "true"',
                    "/app/runtime/staging/go_live_guards/submission_locks.json",
                ),
            ),
            "staging overlay remains isolated",
            "staging overlay is missing its own supervised dry-run values",
            "Keep staging and production overlays separated by their own lock paths and patch files.",
        )
    )

    checks.append(
        _check(
            "staging" not in production_patch.lower() and "/app/runtime/staging" not in production_patch,
            "production overlay separated from staging",
            "production overlay does not reference staging paths",
            "production overlay still references staging paths or labels",
            "Remove staging paths from the production overlay and keep the production lock path separate.",
        )
    )

    checks.append(
        _check(
            not any(marker in all_text for marker in FORBIDDEN_MARKERS),
            "no embedded credentials",
            "no embedded credential markers were found in the package",
            "credential-like markers were found in the package",
            "Keep the manifests placeholder-only and inject real values from a supervised secret manager later.",
        )
    )

    checks.append(
        _check(
            all(path.exists() for path in required_observability_files),
            "observability manifests exist",
            "Prometheus and Grafana manifests are present",
            "one or more observability manifests are missing",
            "Keep Prometheus and Grafana manifests in k8s/base/.",
        )
    )

    checks.append(
        _check(
            all(path.exists() for path in required_storage_files)
            and _contains_all(_text(base_dir / "persistent-volume-claims.yaml"), ("redis-data", "prometheus-data", "grafana-data")),
            "storage placeholders exist",
            "PVC placeholders are present for Redis, Prometheus, and Grafana",
            "PVC placeholders are missing or incomplete",
            "Keep the persistent volume claim placeholders in k8s/base/persistent-volume-claims.yaml.",
        )
    )

    checks.append(
        _check(
            all(path.exists() for path in required_network_policy_files)
            and _contains_all(_text(base_dir / "network-policy.yaml"), ("kind: NetworkPolicy", "default-deny-all")),
            "network policy placeholders exist",
            "network policy placeholders are present",
            "network policy placeholders are missing or incomplete",
            "Keep the network policy placeholder manifests in k8s/base/network-policy.yaml.",
        )
    )

    checks.append(
        _check(
            all(path.exists() for path in required_workload_files),
            "all workload placeholders exist",
            "all workload placeholder manifests are present",
            "one or more workload placeholder manifests are missing",
            "Keep the backend, frontend, worker, Redis, PostgreSQL, Prometheus, and Grafana placeholder manifests.",
        )
    )

    summary_counts = {
        "PASS": sum(1 for check in checks if check.level == "PASS"),
        "FAIL": sum(1 for check in checks if check.level == "FAIL"),
    }
    overall_status = "PASS" if summary_counts["FAIL"] == 0 else "FAIL"
    report = {
        "validation_name": "kubernetes-package",
        "root_dir": str(root_dir),
        "overall_status": overall_status,
        "summary_counts": summary_counts,
        "safety_model": {
            "final_automation_disabled": 'LMCP_ALLOW_FINAL_AUTOMATION: "false"' in production_patch,
            "dry_run_mode_enabled": 'LMCP_DRY_RUN_MODE: "true"' in production_patch,
            "human_supervision_required": 'LMCP_REQUIRE_HUMAN_SUPERVISION: "true"' in production_patch,
            "submission_lock_required": "/app/runtime/production/go_live_guards/submission_locks.json" in production_patch,
            "production_overlay_separated_from_staging": "staging" not in production_patch.lower() and "/app/runtime/staging" not in production_patch,
            "embedded_credentials_found": any(marker in all_text for marker in FORBIDDEN_MARKERS),
        },
        "manifest_inventory": _manifest_inventory(root_dir),
        "checks": [check.__dict__ for check in checks],
        "notes": [
            "This is a scaffold-only Kubernetes package.",
            "No live cluster deployment is authorized by this validator.",
        ],
    }
    return report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the Kubernetes package scaffold.")
    parser.add_argument("--root-dir", default=str(ROOT_DIR), help="Repository root that contains the k8s package.")
    parser.add_argument("--json", action="store_true", help="Emit JSON only.")
    args = parser.parse_args(argv)

    report = build_kubernetes_package_validation_report(root_dir=Path(args.root_dir))
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Kubernetes package validation: {report['overall_status']}")
        print(json.dumps(
            {
                "overall_status": report["overall_status"],
                "summary_counts": report["summary_counts"],
                "safety_model": report["safety_model"],
            },
            indent=2,
            sort_keys=True,
        ))
    return 0 if report["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
