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


def test_kubernetes_package_validation_passes_with_repo_scaffold(capsys) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/validate_kubernetes_package.py"), "validate_kubernetes_package_repo")
    report = module.build_kubernetes_package_validation_report(root_dir=Path("/Users/cash/Documents"))

    assert report["overall_status"] == "PASS"
    assert report["summary_counts"]["FAIL"] == 0
    assert report["safety_model"]["final_automation_disabled"] is True
    assert report["safety_model"]["dry_run_mode_enabled"] is True
    assert report["safety_model"]["human_supervision_required"] is True
    assert report["safety_model"]["submission_lock_required"] is True
    assert report["safety_model"]["production_overlay_separated_from_staging"] is True
    assert report["safety_model"]["embedded_credentials_found"] is False
    assert "k8s/base/backend-deployment.yaml" in report["manifest_inventory"]["workload_files"]
    assert "k8s/base/prometheus-service.yaml" in report["manifest_inventory"]["base_files"]
    assert "k8s/overlays/production/patches/production-safety-patch.yaml" in report["manifest_inventory"]["overlay_files"]

    exit_code = module.main(["--root-dir", "/Users/cash/Documents"])
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Kubernetes package validation: PASS" in output


def test_kubernetes_package_validation_detects_safety_drift_and_missing_manifests(tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/validate_kubernetes_package.py"), "validate_kubernetes_package_bad")
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
    (test_root / "k8s" / "base" / "network-policy.yaml").unlink()
    (test_root / "k8s" / "base" / "persistent-volume-claims.yaml").unlink()
    (test_root / "k8s" / "base" / "prometheus-service.yaml").unlink()

    report = module.build_kubernetes_package_validation_report(root_dir=test_root)

    assert report["overall_status"] == "FAIL"
    failed_checks = {check["name"] for check in report["checks"] if check["level"] == "FAIL"}
    assert "dry-run enforcement exists" in failed_checks
    assert "production overlay safety values preserved" in failed_checks
    assert "no embedded credentials" in failed_checks
    assert "observability manifests exist" in failed_checks
    assert "storage placeholders exist" in failed_checks
    assert "network policy placeholders exist" in failed_checks
