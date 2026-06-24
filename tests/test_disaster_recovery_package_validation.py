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


def test_disaster_recovery_package_validation_passes_with_repo_scaffold(capsys) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/validate_disaster_recovery_package.py"), "validate_disaster_recovery_package_repo")
    report = module.build_disaster_recovery_package_validation_report(root_dir=Path("/Users/cash/Documents"))

    assert report["overall_status"] == "PASS"
    assert report["summary_counts"]["FAIL"] == 0
    assert report["safety_model"]["regional_failover_placeholder_present"] is True
    assert report["safety_model"]["warm_standby_placeholder_present"] is True
    assert report["safety_model"]["dns_failover_placeholder_present"] is True
    assert report["safety_model"]["cross_region_backup_placeholder_present"] is True
    assert report["safety_model"]["dr_rehearsal_job_present"] is True
    assert report["safety_model"]["no_live_cloud_credentials"] is True
    assert report["safety_model"]["no_live_dns_credentials"] is True
    assert report["safety_model"]["rpo_rto_represented"] is True
    assert report["safety_model"]["dry_run_mode_enabled"] is True
    assert report["safety_model"]["human_supervision_required"] is True
    assert "regional-failover-placeholder.yaml" in report["manifest_inventory"]["base_files"]
    assert "warm-standby-placeholder.yaml" in report["manifest_inventory"]["base_files"]
    assert "dns-failover-placeholder.yaml" in report["manifest_inventory"]["base_files"]
    assert "cross-region-backup-placeholder.yaml" in report["manifest_inventory"]["base_files"]
    assert "dr-rehearsal-job-placeholder.yaml" in report["manifest_inventory"]["base_files"]

    exit_code = module.main(["--root-dir", "/Users/cash/Documents"])
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Disaster recovery package validation: PASS" in output


def test_disaster_recovery_package_validation_detects_safety_drift_and_missing_manifests(tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/validate_disaster_recovery_package.py"), "validate_disaster_recovery_package_bad")
    source_root = Path("/Users/cash/Documents")
    test_root = tmp_path / "repo"
    shutil.copytree(source_root / "k8s", test_root / "k8s")

    (test_root / "k8s" / "base" / "regional-failover-placeholder.yaml").unlink()
    dns_file = test_root / "k8s" / "base" / "dns-failover-placeholder.yaml"
    dns_file.write_text(dns_file.read_text(encoding="utf-8") + "\n  cloudflare_api_token: real-dns\n", encoding="utf-8")
    production_patch = test_root / "k8s" / "overlays" / "production" / "patches" / "production-safety-patch.yaml"
    production_patch.write_text(
        production_patch.read_text(encoding="utf-8").replace('LMCP_ALLOW_FINAL_AUTOMATION: "false"', 'LMCP_ALLOW_FINAL_AUTOMATION: "true"'),
        encoding="utf-8",
    )

    report = module.build_disaster_recovery_package_validation_report(root_dir=test_root)

    assert report["overall_status"] == "FAIL"
    failed_checks = {check["name"] for check in report["checks"] if check["level"] == "FAIL"}
    assert "regional failover placeholder exists" in failed_checks
    assert "no live DNS credentials are embedded" in failed_checks
    assert "dry-run remains enforced" in failed_checks
