from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_backup_restore_package_validation_passes_with_repo_scaffold(capsys) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/validate_backup_restore_package.py"), "validate_backup_restore_package_repo")
    report = module.build_backup_restore_package_validation_report(root_dir=Path("/Users/cash/Documents"))

    assert report["overall_status"] == "PASS"
    assert report["summary_counts"]["FAIL"] == 0
    assert report["safety_model"]["postgres_backup_placeholder_present"] is True
    assert report["safety_model"]["redis_persistence_placeholder_present"] is True
    assert report["safety_model"]["backup_storage_secret_placeholder_only"] is True
    assert report["safety_model"]["restore_rehearsal_job_present"] is True
    assert report["safety_model"]["backup_retention_policy_present"] is True
    assert report["safety_model"]["tenant_aware_backup_boundaries_present"] is True
    assert report["safety_model"]["rpo_rto_represented"] is True
    assert report["safety_model"]["dry_run_mode_enabled"] is True
    assert report["safety_model"]["human_supervision_required"] is True
    assert "postgres-backup-cronjob-placeholder.yaml" in report["manifest_inventory"]["base_files"]
    assert "redis-persistence-placeholder.yaml" in report["manifest_inventory"]["base_files"]
    assert "backup-storage-secret-placeholder.yaml" in report["manifest_inventory"]["base_files"]
    assert "restore-rehearsal-job-placeholder.yaml" in report["manifest_inventory"]["base_files"]
    assert "backup-retention-policy-placeholder.yaml" in report["manifest_inventory"]["base_files"]

    exit_code = module.main(["--root-dir", "/Users/cash/Documents"])
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Backup restore package validation: PASS" in output


def test_backup_restore_package_validation_detects_safety_drift_and_missing_manifests(tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/validate_backup_restore_package.py"), "validate_backup_restore_package_bad")
    source_root = Path("/Users/cash/Documents")
    test_root = tmp_path / "repo"
    shutil.copytree(source_root / "k8s", test_root / "k8s")

    backup_secret = test_root / "k8s" / "base" / "backup-storage-secret-placeholder.yaml"
    backup_secret.write_text(
        backup_secret.read_text(encoding="utf-8").replace("placeholder", "real-password"),
        encoding="utf-8",
    )
    restore_job = test_root / "k8s" / "base" / "restore-rehearsal-job-placeholder.yaml"
    restore_job.unlink()
    retention = test_root / "k8s" / "base" / "backup-retention-policy-placeholder.yaml"
    retention.write_text(retention.read_text(encoding="utf-8").replace("rto_minutes: \"120\"", ""), encoding="utf-8")

    report = module.build_backup_restore_package_validation_report(root_dir=test_root)

    assert report["overall_status"] == "FAIL"
    failed_checks = {check["name"] for check in report["checks"] if check["level"] == "FAIL"}
    assert "backup storage secret is placeholder-only" in failed_checks
    assert "restore rehearsal job is represented" in failed_checks
    assert "backup retention policy is represented" in failed_checks or "RPO/RTO values are represented" in failed_checks
