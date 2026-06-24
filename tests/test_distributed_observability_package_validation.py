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


def test_distributed_observability_package_validation_passes_with_repo_scaffold(capsys) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/validate_distributed_observability_package.py"), "validate_distributed_observability_package_repo")
    report = module.build_distributed_observability_package_validation_report(root_dir=Path("/Users/cash/Documents"))

    assert report["overall_status"] == "PASS"
    assert report["summary_counts"]["FAIL"] == 0
    assert report["safety_model"]["final_automation_disabled"] is True
    assert report["safety_model"]["dry_run_mode_enabled"] is True
    assert report["safety_model"]["human_supervision_required"] is True
    assert report["safety_model"]["submission_lock_required"] is True
    assert report["safety_model"]["production_overlay_separated_from_staging"] is True
    assert report["safety_model"]["embedded_credentials_found"] is False
    assert report["safety_model"]["no_live_telemetry_endpoints"] is True
    assert report["safety_model"]["no_external_alert_delivery"] is True
    assert "loki-placeholder.yaml" in report["manifest_inventory"]["base_files"]
    assert "tempo-placeholder.yaml" in report["manifest_inventory"]["base_files"]
    assert "distributed-prometheus-placeholder.yaml" in report["manifest_inventory"]["base_files"]
    assert "alertmanager-placeholder.yaml" in report["manifest_inventory"]["base_files"]

    exit_code = module.main(["--root-dir", "/Users/cash/Documents"])
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Distributed observability package validation: PASS" in output


def test_distributed_observability_package_validation_detects_safety_drift_and_missing_manifests(tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/validate_distributed_observability_package.py"), "validate_distributed_observability_package_bad")
    source_root = Path("/Users/cash/Documents")
    test_root = tmp_path / "repo"
    shutil.copytree(source_root / "k8s", test_root / "k8s")

    production_patch = test_root / "k8s" / "overlays" / "production" / "patches" / "production-safety-patch.yaml"
    production_patch.write_text(
        production_patch.read_text(encoding="utf-8")
        .replace('LMCP_ALLOW_FINAL_AUTOMATION: "false"', 'LMCP_ALLOW_FINAL_AUTOMATION: "true"')
        .replace('LMCP_DRY_RUN_MODE: "true"', 'LMCP_DRY_RUN_MODE: "false"')
        + "\n# real-password should never be here\n",
        encoding="utf-8",
    )
    alertmanager_file = test_root / "k8s" / "base" / "alertmanager-placeholder.yaml"
    alertmanager_file.write_text(
        alertmanager_file.read_text(encoding="utf-8") + "\nwebhook_configs:\n  - url: https://example.com/alerts\n",
        encoding="utf-8",
    )
    (test_root / "k8s" / "base" / "tempo-placeholder.yaml").unlink()
    (test_root / "k8s" / "base" / "distributed-prometheus-placeholder.yaml").unlink()

    report = module.build_distributed_observability_package_validation_report(root_dir=test_root)

    assert report["overall_status"] == "FAIL"
    failed_checks = {check["name"] for check in report["checks"] if check["level"] == "FAIL"}
    assert "dry-run enforcement exists" in failed_checks
    assert "final automation disabled" in failed_checks
    assert "no embedded credentials" in failed_checks
    assert "tempo placeholder exists" in failed_checks
    assert "distributed prometheus placeholder exists" in failed_checks
    assert "no external alert delivery" in failed_checks
