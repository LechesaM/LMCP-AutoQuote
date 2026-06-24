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
    BASE_DIR / "regional-failover-placeholder.yaml",
    BASE_DIR / "warm-standby-placeholder.yaml",
    BASE_DIR / "dns-failover-placeholder.yaml",
    BASE_DIR / "cross-region-backup-placeholder.yaml",
    BASE_DIR / "dr-rehearsal-job-placeholder.yaml",
]
REQUIRED_OVERLAY_FILES = [STAGING_PATCH, PRODUCTION_PATCH]
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
DNS_FORBIDDEN_MARKERS = [
    "dns_api_key",
    "dns_secret",
    "dns_password",
    "cloudflare_api_token",
    "route53_secret",
    "real-dns",
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
    return CheckResult("PASS", name, pass_message) if condition else CheckResult("FAIL", name, fail_message, remediation)


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


def build_disaster_recovery_package_validation_report(root_dir: Optional[Path] = None) -> Dict[str, Any]:
    root_dir = root_dir or ROOT_DIR
    k8s_root = root_dir / "k8s"
    base_dir = k8s_root / "base"
    production_patch = root_dir / "k8s" / "overlays" / "production" / "patches" / "production-safety-patch.yaml"
    staging_patch = root_dir / "k8s" / "overlays" / "staging" / "patches" / "staging-safety-patch.yaml"

    regional = base_dir / "regional-failover-placeholder.yaml"
    standby = base_dir / "warm-standby-placeholder.yaml"
    dns = base_dir / "dns-failover-placeholder.yaml"
    cross_region = base_dir / "cross-region-backup-placeholder.yaml"
    rehearsal = base_dir / "dr-rehearsal-job-placeholder.yaml"

    production_text = _text(production_patch)
    staging_text = _text(staging_patch)
    all_text = _load_all_text(k8s_root)

    checks: List[CheckResult] = []
    checks.append(_check(all(path.exists() for path in REQUIRED_DIRECTORIES), "required manifest directories exist", "k8s package directories are present", "one or more required k8s package directories are missing", "Create k8s/base/, k8s/overlays/staging/, and k8s/overlays/production/."))
    checks.append(_check(all(path.exists() for path in REQUIRED_BASE_FILES), "required workload manifests exist", "all required DR governance manifests are present", "one or more required DR governance manifests are missing", "Keep the DR placeholders in k8s/base/."))
    checks.append(_check(all(path.exists() for path in REQUIRED_OVERLAY_FILES), "overlay manifests exist", "staging and production overlays are present", "one or more overlay manifests are missing", "Create the staging and production overlay safety patches."))

    regional_ready = regional.exists() and _contains_all(_text(regional), ["regional-failover-placeholder", "kind: ConfigMap", "regional_failover", "failover_region", "rpo_minutes", "rto_minutes"])
    standby_ready = standby.exists() and _contains_all(_text(standby), ["warm-standby-placeholder", "kind: Deployment", "standby_mode", "standby_region", "replicas:"])
    dns_ready = dns.exists() and _contains_all(_text(dns), ["dns-failover-placeholder", "kind: ConfigMap", "dns_failover", "primary_dns_record", "failover_dns_record", "dns_provider"])
    cross_region_ready = cross_region.exists() and _contains_all(_text(cross_region), ["cross-region-backup-placeholder", "kind: CronJob", "cross_region_backup", "backup_region", "rpo_minutes"])
    rehearsal_ready = rehearsal.exists() and _contains_all(_text(rehearsal), ["dr-rehearsal-job-placeholder", "kind: Job", "dr_rehearsal", "failover_drill", "rto_minutes"])
    no_live_cloud_credentials = not any(marker in all_text for marker in FORBIDDEN_MARKERS)
    no_live_dns_credentials = not any(marker in all_text.lower() for marker in DNS_FORBIDDEN_MARKERS)
    rpo_rto_represented = _contains_all(_text(regional), ["rpo_minutes", "rto_minutes"]) and _contains_all(_text(dns), ["rto_minutes"]) and _contains_all(_text(rehearsal), ["rto_minutes"])
    safety_controls_ready = _contains_all(
        production_text,
        [
            'LMCP_ALLOW_FINAL_AUTOMATION: "false"',
            'LMCP_DRY_RUN_MODE: "true"',
            'LMCP_REQUIRE_HUMAN_SUPERVISION: "true"',
            "LMCP_SUBMISSION_LOCK_FILE:",
        ],
    )
    overlays_separated = "LMCP_ENV: staging" in staging_text and "LMCP_ENV: production" in production_text

    checks.append(_check(regional_ready, "regional failover placeholder exists", "regional failover placeholder is present", "regional failover placeholder is missing", "Keep the regional failover placeholder in the base package."))
    checks.append(_check(standby_ready, "warm standby placeholder exists", "warm standby placeholder is present", "warm standby placeholder is missing", "Keep the warm standby placeholder in the base package."))
    checks.append(_check(dns_ready, "DNS failover placeholder exists", "DNS failover placeholder is present", "DNS failover placeholder is missing", "Keep the DNS failover placeholder in the base package."))
    checks.append(_check(cross_region_ready, "cross-region backup placeholder exists", "cross-region backup placeholder is present", "cross-region backup placeholder is missing", "Keep the cross-region backup placeholder in the base package."))
    checks.append(_check(rehearsal_ready, "DR rehearsal job exists", "DR rehearsal job placeholder is present", "DR rehearsal job placeholder is missing", "Keep the DR rehearsal job placeholder in the base package."))
    checks.append(_check(no_live_cloud_credentials, "no live cloud credentials are embedded", "no live cloud credentials were detected", "live cloud credentials were detected", "Keep all cloud credentials placeholder-only."))
    checks.append(_check(no_live_dns_credentials, "no live DNS credentials are embedded", "no live DNS credentials were detected", "live DNS credentials were detected", "Keep all DNS credentials placeholder-only."))
    checks.append(_check(rpo_rto_represented, "RPO/RTO escalation is represented", "RPO and RTO escalation values are represented", "RPO and RTO escalation values are missing", "Keep RPO and RTO values in the DR placeholders."))
    checks.append(_check(safety_controls_ready, "dry-run remains enforced", "production overlay keeps final automation disabled, dry-run enabled, and submission locks enforced", "production safety controls are incomplete", "Keep final automation disabled, dry-run enabled, and submission locks enforced in production."))
    checks.append(_check('LMCP_REQUIRE_HUMAN_SUPERVISION: "true"' in production_text, "supervision remains mandatory", "human supervision remains mandatory in the production overlay", "human supervision is not mandatory in the production overlay", "Keep LMCP_REQUIRE_HUMAN_SUPERVISION set to true in production."))
    checks.append(_check(overlays_separated, "staging and production overlays remain separated", "staging and production overlays are separated", "staging and production overlays are not separated", "Keep staging and production overlays distinct."))

    summary_counts = {
        "PASS": len([check for check in checks if check.level == "PASS"]),
        "WARN": 0,
        "FAIL": len([check for check in checks if check.level == "FAIL"]),
    }
    overall_status = "PASS" if summary_counts["FAIL"] == 0 else "FAIL"
    safety_model = {
        "regional_failover_placeholder_present": regional_ready,
        "warm_standby_placeholder_present": standby_ready,
        "dns_failover_placeholder_present": dns_ready,
        "cross_region_backup_placeholder_present": cross_region_ready,
        "dr_rehearsal_job_present": rehearsal_ready,
        "no_live_cloud_credentials": no_live_cloud_credentials,
        "no_live_dns_credentials": no_live_dns_credentials,
        "rpo_rto_represented": rpo_rto_represented,
        "dry_run_mode_enabled": 'LMCP_DRY_RUN_MODE: "true"' in production_text,
        "human_supervision_required": 'LMCP_REQUIRE_HUMAN_SUPERVISION: "true"' in production_text,
        "production_overlay_separated_from_staging": overlays_separated,
        "embedded_credentials_found": any(marker in all_text for marker in FORBIDDEN_MARKERS),
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
    parser = argparse.ArgumentParser(description="Validate the disaster recovery package.")
    parser.add_argument("--root-dir", default=str(ROOT_DIR), help="Repository root to validate.")
    args = parser.parse_args(argv)
    report = build_disaster_recovery_package_validation_report(root_dir=Path(args.root_dir))
    print(f"Disaster recovery package validation: {report['overall_status']}")
    for check in report["checks"]:
        print(f"[{check['level']}] {check['name']}: {check['message']}")
        if check["level"] == "FAIL" and check["remediation"]:
            print(f"  remediation: {check['remediation']}")
    return 0 if report["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
