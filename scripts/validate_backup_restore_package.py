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
    BASE_DIR / "postgres-backup-cronjob-placeholder.yaml",
    BASE_DIR / "redis-persistence-placeholder.yaml",
    BASE_DIR / "backup-storage-secret-placeholder.yaml",
    BASE_DIR / "restore-rehearsal-job-placeholder.yaml",
    BASE_DIR / "backup-retention-policy-placeholder.yaml",
    BASE_DIR / "tenant-namespace-template.yaml",
    BASE_DIR / "tenant-network-policy-template.yaml",
    BASE_DIR / "tenant-rbac-placeholder.yaml",
    BASE_DIR / "tenant-resource-quota-placeholder.yaml",
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


def build_backup_restore_package_validation_report(root_dir: Optional[Path] = None) -> Dict[str, Any]:
    root_dir = root_dir or ROOT_DIR
    k8s_root = root_dir / "k8s"
    base_dir = k8s_root / "base"
    staging_dir = k8s_root / "overlays" / "staging"
    production_dir = k8s_root / "overlays" / "production"

    postgres_backup = base_dir / "postgres-backup-cronjob-placeholder.yaml"
    redis_persistence = base_dir / "redis-persistence-placeholder.yaml"
    backup_secret = base_dir / "backup-storage-secret-placeholder.yaml"
    restore_rehearsal = base_dir / "restore-rehearsal-job-placeholder.yaml"
    retention_policy = base_dir / "backup-retention-policy-placeholder.yaml"
    tenant_namespace = base_dir / "tenant-namespace-template.yaml"
    tenant_network = base_dir / "tenant-network-policy-template.yaml"
    tenant_rbac = base_dir / "tenant-rbac-placeholder.yaml"
    tenant_quota = base_dir / "tenant-resource-quota-placeholder.yaml"

    production_text = _text(PRODUCTION_PATCH)
    staging_text = _text(STAGING_PATCH)
    secret_text = _text(backup_secret)
    all_text = _load_all_text(k8s_root)

    checks: List[CheckResult] = []
    checks.append(_check(all(path.exists() for path in REQUIRED_DIRECTORIES), "required manifest directories exist", "k8s package directories are present", "one or more required k8s package directories are missing", "Create k8s/base/, k8s/overlays/staging/, and k8s/overlays/production/."))
    checks.append(_check(all(path.exists() for path in REQUIRED_BASE_FILES), "required workload manifests exist", "all required backup governance manifests are present", "one or more required backup governance manifests are missing", "Keep the backup, restore, and durability placeholders in k8s/base/."))
    checks.append(_check(all(path.exists() for path in REQUIRED_OVERLAY_FILES), "overlay manifests exist", "staging and production overlays are present", "one or more overlay manifests are missing", "Create the staging and production overlay safety patches."))

    required_controls = (
        'LMCP_ALLOW_FINAL_AUTOMATION: "false"',
        'LMCP_DRY_RUN_MODE: "true"',
        'LMCP_REQUIRE_HUMAN_SUPERVISION: "true"',
        'LMCP_SUBMISSION_LOCK_FILE:',
    )

    postgres_backup_ready = postgres_backup.exists() and _contains_all(_text(postgres_backup), ["postgres-backup-cronjob-placeholder", "kind: CronJob", "pg_dump", "rpo_minutes"])
    redis_persistence_ready = redis_persistence.exists() and _contains_all(_text(redis_persistence), ["redis-persistence-placeholder", "PersistentVolumeClaim", "persistence_enabled", "backup_safe"])
    backup_secret_placeholder_only = backup_secret.exists() and _contains_all(secret_text, ["backup-storage-secret-placeholder", "placeholder", "backup_endpoint", "backup_access_key", "backup_secret_key", "encryption_at_rest"]) and not any(
        marker in secret_text for marker in FORBIDDEN_MARKERS
    )
    restore_rehearsal_ready = restore_rehearsal.exists() and _contains_all(_text(restore_rehearsal), ["restore-rehearsal-job-placeholder", "kind: Job", "restore_validation", "rto_minutes"])
    retention_policy_ready = retention_policy.exists() and _contains_all(_text(retention_policy), ["backup-retention-policy-placeholder", "retention_days", "retention_policy", "rpo_minutes", "rto_minutes"])
    tenant_boundaries_ready = all(
        [
            tenant_namespace.exists() and _contains_all(_text(tenant_namespace), ["tenant-namespace-template-placeholder", 'lmcp.io/tenant-segregation: "enabled"', 'lmcp.io/tenant-onboarding: "disabled"']),
            tenant_network.exists() and _contains_all(_text(tenant_network), ["tenant-network-policy-template-placeholder", "policyTypes"]),
            tenant_rbac.exists() and _contains_all(_text(tenant_rbac), ["tenant-rbac-placeholder", "verbs:"]),
            tenant_quota.exists() and _contains_all(_text(tenant_quota), ["tenant-resource-quota-placeholder", "requests.cpu"]),
        ]
    )
    rpo_rto_represented = _contains_all(_text(postgres_backup), ["rpo_minutes"]) and _contains_all(_text(restore_rehearsal), ["rto_minutes"]) and _contains_all(_text(retention_policy), ["rpo_minutes", "rto_minutes"])
    no_live_external_storage_credentials = not any(marker in all_text.lower() for marker in ["aws_access_key_id", "aws_secret_access_key", "s3://", "gs://", "azblob", "minio-prod", "bucket-prod"])

    checks.append(_check(postgres_backup_ready, "PostgreSQL backup placeholder exists", "PostgreSQL backup placeholder is present", "PostgreSQL backup placeholder is missing", "Keep the PostgreSQL backup CronJob placeholder in the base package."))
    checks.append(_check(redis_persistence_ready, "Redis persistence placeholder exists", "Redis persistence placeholder is present", "Redis persistence placeholder is missing", "Keep the Redis persistence placeholder in the base package."))
    checks.append(_check(backup_secret_placeholder_only, "backup storage secret is placeholder-only", "backup storage secret is placeholder-only", "backup storage secret contains non-placeholder content", "Keep the backup storage secret limited to placeholder values."))
    checks.append(_check(restore_rehearsal_ready, "restore rehearsal job is represented", "restore rehearsal job placeholder is present", "restore rehearsal job placeholder is missing", "Keep the restore rehearsal job placeholder in the base package."))
    checks.append(_check(retention_policy_ready, "backup retention policy is represented", "backup retention policy placeholder is present", "backup retention policy placeholder is missing", "Keep the backup retention policy placeholder in the base package."))
    checks.append(_check(no_live_external_storage_credentials, "no live external storage credentials are embedded", "no live external storage credentials were detected", "live external storage credentials were detected", "Keep external storage credentials placeholder-only."))
    checks.append(_check(tenant_boundaries_ready, "tenant-aware backup boundaries are represented", "tenant-aware backup boundaries are present", "tenant-aware backup boundaries are missing", "Keep tenant namespace, network policy, RBAC, and quota placeholders in the base package."))
    checks.append(_check(rpo_rto_represented, "RPO/RTO values are represented", "RPO and RTO values are represented", "RPO and RTO values are missing", "Keep RPO and RTO placeholders in the backup retention and restore rehearsal manifests."))
    checks.append(_check(_contains_all(production_text, required_controls), "dry-run remains enforced", "production overlay keeps final automation disabled, dry-run enabled, and supervision required", "production safety controls are incomplete", "Keep final automation disabled, dry-run enabled, and human supervision required in the production overlay."))
    checks.append(_check('LMCP_REQUIRE_HUMAN_SUPERVISION: "true"' in production_text, "supervision remains mandatory", "human supervision remains mandatory in the production overlay", "human supervision is not mandatory in the production overlay", "Keep LMCP_REQUIRE_HUMAN_SUPERVISION set to true in production."))

    summary_counts = {
        "PASS": len([check for check in checks if check.level == "PASS"]),
        "WARN": 0,
        "FAIL": len([check for check in checks if check.level == "FAIL"]),
    }
    overall_status = "PASS" if summary_counts["FAIL"] == 0 else "FAIL"
    safety_model = {
        "postgres_backup_placeholder_present": postgres_backup_ready,
        "redis_persistence_placeholder_present": redis_persistence_ready,
        "backup_storage_secret_placeholder_only": backup_secret_placeholder_only,
        "restore_rehearsal_job_present": restore_rehearsal_ready,
        "backup_retention_policy_present": retention_policy_ready,
        "tenant_aware_backup_boundaries_present": tenant_boundaries_ready,
        "rpo_rto_represented": rpo_rto_represented,
        "dry_run_mode_enabled": "LMCP_DRY_RUN_MODE: \"true\"" in production_text,
        "human_supervision_required": "LMCP_REQUIRE_HUMAN_SUPERVISION: \"true\"" in production_text,
        "production_overlay_separated_from_staging": "LMCP_ENV: staging" in staging_text and "LMCP_ENV: production" in production_text,
        "embedded_credentials_found": any(marker in all_text for marker in FORBIDDEN_MARKERS),
        "live_external_storage_credentials_found": not no_live_external_storage_credentials,
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
    parser = argparse.ArgumentParser(description="Validate the backup restore package.")
    parser.add_argument("--root-dir", default=str(ROOT_DIR), help="Repository root to validate.")
    args = parser.parse_args(argv)
    report = build_backup_restore_package_validation_report(root_dir=Path(args.root_dir))
    print(f"Backup restore package validation: {report['overall_status']}")
    for check in report["checks"]:
        print(f"[{check['level']}] {check['name']}: {check['message']}")
        if check["level"] == "FAIL" and check["remediation"]:
            print(f"  remediation: {check['remediation']}")
    return 0 if report["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
