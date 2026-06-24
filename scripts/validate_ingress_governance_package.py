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
    BASE_DIR / "ingress.yaml",
    BASE_DIR / "tls-secret-placeholder.yaml",
    BASE_DIR / "cert-manager-placeholder.yaml",
]
REQUIRED_OVERLAY_FILES = [
    STAGING_DIR / "kustomization.yaml",
    STAGING_DIR / "patches" / "staging-safety-patch.yaml",
    PRODUCTION_DIR / "kustomization.yaml",
    PRODUCTION_DIR / "patches" / "production-safety-patch.yaml",
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


def _check(condition: bool, name: str, pass_message: str, fail_message: str, remediation: str = "") -> CheckResult:
    if condition:
        return CheckResult("PASS", name, pass_message)
    return CheckResult("FAIL", name, fail_message, remediation)


def _contains_all(text: str, needles: Iterable[str]) -> bool:
    return all(needle in text for needle in needles)


def _load_all_text(root_dir: Path) -> str:
    parts: List[str] = []
    for path in root_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".yaml", ".yml", ".md"}:
            try:
                parts.append(path.read_text(encoding="utf-8"))
            except Exception:
                continue
    return "\n".join(parts)


def build_ingress_governance_package_validation_report(root_dir: Optional[Path] = None) -> Dict[str, Any]:
    root_dir = root_dir or ROOT_DIR
    k8s_root = root_dir / "k8s"
    base_dir = k8s_root / "base"
    staging_dir = k8s_root / "overlays" / "staging"
    production_dir = k8s_root / "overlays" / "production"
    staging_patch = staging_dir / "patches" / "staging-safety-patch.yaml"
    production_patch = production_dir / "patches" / "production-safety-patch.yaml"
    ingress_file = base_dir / "ingress.yaml"
    cert_file = base_dir / "cert-manager-placeholder.yaml"
    tls_file = base_dir / "tls-secret-placeholder.yaml"

    checks: List[CheckResult] = []
    checks.append(_check(all(path.exists() for path in REQUIRED_DIRECTORIES), "required manifest directories exist", "k8s package directories are present", "one or more required k8s package directories are missing", "Create k8s/base/, k8s/overlays/staging/, and k8s/overlays/production/."))
    checks.append(_check(all(path.exists() for path in REQUIRED_BASE_FILES), "required workload manifests exist", "all required base workload manifests are present", "one or more required base manifests are missing", "Keep the ingress, TLS secret placeholder, and cert-manager placeholder in k8s/base/."))
    checks.append(_check(all(path.exists() for path in REQUIRED_OVERLAY_FILES), "overlay manifests exist", "staging and production overlays are present", "one or more overlay manifests are missing", "Create the staging and production overlay kustomization files and patches."))

    production_text = _text(production_patch)
    staging_text = _text(staging_patch)
    ingress_text = _text(ingress_file)
    cert_text = _text(cert_file)
    tls_text = _text(tls_file)
    all_text = _load_all_text(k8s_root)

    required_controls = (
        'LMCP_ALLOW_FINAL_AUTOMATION: "false"',
        'LMCP_DRY_RUN_MODE: "true"',
        'LMCP_REQUIRE_HUMAN_SUPERVISION: "true"',
        'LMCP_SUBMISSION_LOCK_FILE:',
    )

    checks.append(_check(_contains_all(production_text, required_controls), "dry-run enforcement exists", "production overlay keeps final automation disabled, dry-run enabled, and supervision required", "production safety controls are incomplete", "Keep final automation disabled, dry-run enabled, and human supervision required in the production overlay."))
    checks.append(_check("LMCP_ENV: staging" in staging_text and "LMCP_ENV: production" in production_text, "production overlay separated from staging", "staging and production overlays declare distinct environments", "staging and production overlays are not clearly separated", "Keep staging and production overlays separated by their own patch files and environment values."))
    checks.append(_check(_contains_all(production_text, required_controls), "final automation disabled", "final automation remains disabled in the production overlay", "final automation is not disabled in the production overlay", "Keep LMCP_ALLOW_FINAL_AUTOMATION set to false in production."))
    checks.append(_check('LMCP_REQUIRE_HUMAN_SUPERVISION: "true"' in production_text, "supervision mandatory", "human supervision remains mandatory in the production overlay", "human supervision is not mandatory in the production overlay", "Keep LMCP_REQUIRE_HUMAN_SUPERVISION set to true in production."))
    checks.append(_check(not any(marker in all_text for marker in FORBIDDEN_MARKERS), "no embedded credentials", "no embedded credentials were detected", "embedded credentials or secrets were detected in the package", "Keep only placeholder secrets and no production credentials in the package."))
    checks.append(_check(all(path.exists() for path in [base_dir / "prometheus-deployment.yaml", base_dir / "prometheus-service.yaml", base_dir / "grafana-deployment.yaml", base_dir / "grafana-service.yaml"]), "observability manifests exist", "observability manifests are present", "observability manifests are missing", "Keep Prometheus and Grafana manifests in the base package."))
    checks.append(_check(all(path.exists() for path in [base_dir / "persistent-volume-claims.yaml"]), "storage placeholders exist", "storage placeholder manifests are present", "storage placeholder manifests are missing", "Keep persistent volume claim placeholders in the base package."))
    checks.append(_check(all(path.exists() for path in [base_dir / "network-policy.yaml"]), "network policy placeholders exist", "network policy placeholder manifests are present", "network policy placeholder manifests are missing", "Keep network policy placeholders in the base package."))
    checks.append(_check(_contains_all(ingress_text, ["ingressClassName: internal-placeholder", 'lmcp.io/public-exposure: "disabled"', 'lmcp.io/internal-routing: "enabled"', 'lmcp.io/external-routing: "disabled"', 'lmcp.io/admin-access: "internal-only"', 'lmcp.io/observability-access: "internal-only"', "placeholder.lmcp.local", "tls-secret-placeholder"]), "ingress placeholders exist", "ingress placeholder manifest is present and internal-only", "ingress placeholder manifest is missing the staged safety markers", "Keep the ingress placeholder internal-only and tied to placeholder host and secret names."))
    checks.append(_check(_contains_all(cert_text, ["placeholder-issuer", "tls-secret-placeholder", "placeholder.lmcp.local"]), "cert-manager placeholder exists", "certificate governance placeholder is present", "certificate governance placeholder is incomplete", "Keep the cert-manager placeholder bound to placeholder issuer and host names."))
    checks.append(_check(_contains_all(tls_text, ["tls.crt:", "tls.key:"]), "tls secret placeholder exists", "TLS secret placeholder is present", "TLS secret placeholder is incomplete", "Keep the TLS secret placeholder in the base package."))
    checks.append(_check("letsencrypt" not in ingress_text.lower() and "letsencrypt" not in cert_text.lower() and "example.com" not in ingress_text.lower() and "example.com" not in cert_text.lower(), "no live DNS or certificates", "no live DNS or certificate references were detected", "live DNS or certificate references were detected", "Keep all ingress and certificate markers on placeholder hostnames and issuers only."))
    checks.append(_check('lmcp.io/public-exposure: "disabled"' in ingress_text, "no public exposure enablement", "public exposure remains disabled in the ingress placeholder", "public exposure is enabled in the ingress placeholder", "Keep public exposure disabled in the ingress placeholder."))

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
        "public_exposure_disabled": 'lmcp.io/public-exposure: "disabled"' in ingress_text,
        "live_dns_found": any(marker in ingress_text.lower() for marker in ["letsencrypt", "example.com", "public.example", "https://"]),
        "live_certificate_found": any(marker in cert_text.lower() for marker in ["letsencrypt", "example.com", "cluster-issuer: letsencrypt"]),
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
    parser = argparse.ArgumentParser(description="Validate the ingress governance package.")
    parser.add_argument("--root-dir", default=str(ROOT_DIR), help="Repository root to validate.")
    args = parser.parse_args(argv)
    report = build_ingress_governance_package_validation_report(root_dir=Path(args.root_dir))
    print(f"Ingress governance package validation: {report['overall_status']}")
    for check in report["checks"]:
        print(f"[{check['level']}] {check['name']}: {check['message']}")
        if check["level"] == "FAIL" and check["remediation"]:
            print(f"  remediation: {check['remediation']}")
    return 0 if report["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
