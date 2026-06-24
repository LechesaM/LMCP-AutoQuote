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


def test_autoscaling_package_validation_passes_with_repo_scaffold(capsys) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/validate_autoscaling_package.py"), "validate_autoscaling_package_repo")
    report = module.build_autoscaling_package_validation_report(root_dir=Path("/Users/cash/Documents"))

    assert report["overall_status"] == "PASS"
    assert report["summary_counts"]["FAIL"] == 0
    assert report["safety_model"]["hpa_placeholders_present"] is True
    assert report["safety_model"]["resource_requests_limits_present"] is True
    assert report["safety_model"]["namespace_resource_quotas_present"] is True
    assert report["safety_model"]["limit_ranges_present"] is True
    assert report["safety_model"]["queue_depth_scaling_present"] is True
    assert report["safety_model"]["tenant_aware_scaling_boundaries_present"] is True
    assert report["safety_model"]["no_autonomous_production_authority"] is True
    assert report["safety_model"]["dry_run_mode_enabled"] is True
    assert report["safety_model"]["human_supervision_required"] is True
    assert report["safety_model"]["external_alert_delivery_disabled"] is True
    assert "backend-hpa-placeholder.yaml" in report["manifest_inventory"]["base_files"]
    assert "frontend-hpa-placeholder.yaml" in report["manifest_inventory"]["base_files"]
    assert "worker-hpa-placeholder.yaml" in report["manifest_inventory"]["base_files"]
    assert "resource-quota-placeholder.yaml" in report["manifest_inventory"]["base_files"]
    assert "limit-range-placeholder.yaml" in report["manifest_inventory"]["base_files"]
    assert "queue-depth-scaling-placeholder.yaml" in report["manifest_inventory"]["base_files"]

    exit_code = module.main(["--root-dir", "/Users/cash/Documents"])
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Autoscaling package validation: PASS" in output


def test_autoscaling_package_validation_detects_safety_drift_and_missing_manifests(tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/validate_autoscaling_package.py"), "validate_autoscaling_package_bad")
    source_root = Path("/Users/cash/Documents")
    test_root = tmp_path / "repo"
    shutil.copytree(source_root / "k8s", test_root / "k8s")

    backend_hpa = test_root / "k8s" / "base" / "backend-hpa-placeholder.yaml"
    backend_hpa.unlink()
    queue_depth = test_root / "k8s" / "base" / "queue-depth-scaling-placeholder.yaml"
    queue_depth.write_text(queue_depth.read_text(encoding="utf-8").replace("scale_down_threshold: placeholder", ""), encoding="utf-8")
    alertmanager = test_root / "k8s" / "base" / "alertmanager-placeholder.yaml"
    alertmanager.write_text(alertmanager.read_text(encoding="utf-8") + "\n  webhook_configs:\n    - url: https://alerts.example.invalid\n", encoding="utf-8")
    production_patch = test_root / "k8s" / "overlays" / "production" / "patches" / "production-safety-patch.yaml"
    production_patch.write_text(
        production_patch.read_text(encoding="utf-8").replace('LMCP_ALLOW_FINAL_AUTOMATION: "false"', 'LMCP_ALLOW_FINAL_AUTOMATION: "true"'),
        encoding="utf-8",
    )

    report = module.build_autoscaling_package_validation_report(root_dir=test_root)

    assert report["overall_status"] == "FAIL"
    failed_checks = {check["name"] for check in report["checks"] if check["level"] == "FAIL"}
    assert "HPA placeholders exist" in failed_checks
    assert "queue-depth scaling is represented" in failed_checks
    assert "no autonomous production authority is introduced" in failed_checks
    assert "external alert delivery remains disabled" in failed_checks
