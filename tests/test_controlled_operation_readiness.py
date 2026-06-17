from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_controlled_operation_readiness_reports_ready_when_thresholds_are_met(monkeypatch, tmp_path: Path, capsys) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/check_controlled_operation_readiness.py"), "controlled_operation_ready")
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module, "build_pilot_readiness_report", lambda limit=20: {"pilot_readiness_score": 90.0})
    monkeypatch.setattr(module, "get_pilot_summary", lambda: {"total_runs": 3, "successful_runs": 2, "failed_runs": 1})
    monkeypatch.setattr(module, "get_pilot_signoffs", lambda: [{"signoff_type": "approval", "signoff_status": "signed"}, {"signoff_type": "proof", "signoff_status": "signed"}])
    monkeypatch.setattr(module, "get_pilot_execution_metadata", lambda: {"pilot_enabled": True, "pilot_mode": "supervised_live"})
    monkeypatch.setattr(
        module,
        "get_runtime_paths",
        lambda: type(
            "P",
            (),
            {
                "project_root": tmp_path,
                "runtime_root": tmp_path / "runtime",
                "manual_production_dir": tmp_path / "manual_production",
            },
        )(),
    )
    for path in [
        tmp_path / "docs" / "controlled_operation_checklist.md",
        tmp_path / "docs" / "supervised_live_pilot_runbook.md",
        tmp_path / "docs" / "supervised_live_daily_checklist.md",
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ok", encoding="utf-8")

    report = module.build_controlled_operation_readiness_report(limit=5)
    assert report["controlled_operation_ready"] is True
    assert report["thresholds"]["readiness_score"] == 90.0
    assert report["thresholds"]["blockers"] == []

    exit_code = module.main(["--json"])
    output = capsys.readouterr().out
    assert exit_code == 0
    payload = json.loads(output)
    assert payload["controlled_operation_ready"] is True


def test_controlled_operation_readiness_blocks_when_evidence_is_missing(monkeypatch, tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/check_controlled_operation_readiness.py"), "controlled_operation_not_ready")
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module, "build_pilot_readiness_report", lambda limit=20: {"pilot_readiness_score": 70.0})
    monkeypatch.setattr(module, "get_pilot_summary", lambda: {"total_runs": 0, "successful_runs": 0, "failed_runs": 0})
    monkeypatch.setattr(module, "get_pilot_signoffs", lambda: [])
    monkeypatch.setattr(module, "get_pilot_execution_metadata", lambda: {"pilot_enabled": True, "pilot_mode": "supervised_live"})
    monkeypatch.setattr(
        module,
        "get_runtime_paths",
        lambda: type(
            "P",
            (),
            {
                "project_root": tmp_path,
                "runtime_root": tmp_path / "runtime",
                "manual_production_dir": tmp_path / "manual_production",
            },
        )(),
    )

    report = module.build_controlled_operation_readiness_report(limit=5)
    assert report["controlled_operation_ready"] is False
    assert report["blockers"]
