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


def test_run_workspace_pilot_uses_pilot_folder(tmp_path: Path, monkeypatch, capsys) -> None:
    workspace = tmp_path / "lmcp_pilot_runs"
    pilot_dir = workspace / "PILOT-001"
    (pilot_dir / "rfq_source").mkdir(parents=True, exist_ok=True)
    (pilot_dir / "submission_logs").mkdir(parents=True, exist_ok=True)
    (pilot_dir / "submission_logs" / "pilot_status.json").write_text(
        json.dumps({"rfq_number": "REAL-PILOT-001"}),
        encoding="utf-8",
    )
    pricing_file = pilot_dir / "generated_package" / "pricing.json"
    pricing_file.parent.mkdir(parents=True, exist_ok=True)
    pricing_file.write_text(json.dumps({"items": []}), encoding="utf-8")
    (pilot_dir / "pilot_manifest.json").write_text(
        json.dumps(
            {
                "pilot_scope": ["supply_and_delivery_only"],
                "success_criteria": ["submission_ready"],
                "pricing_file": "generated_package/pricing.json",
            }
        ),
        encoding="utf-8",
    )

    module = _load_module(Path("/Users/cash/Documents/scripts/run_workspace_pilot.py"), "run_workspace_pilot")

    captured = {}

    def _fake_run_manual_pilot(**kwargs):
        captured.update(kwargs)
        return {
            "status": "warning",
            "submission_ready": False,
            "quote_pack_quality_status": "approval_ready",
            "approval_blocked": False,
        }

    monkeypatch.setattr(module, "run_manual_pilot", _fake_run_manual_pilot)

    exit_code = module.main(["--workspace-root", str(workspace), "--pilot-id", "PILOT-001"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert captured["tender_root"] == str(pilot_dir / "rfq_source")
    assert captured["tender_id"] == "REAL-PILOT-001"
    assert captured["pricing_file"] == str(pricing_file)
    assert captured["workspace_root"] == str(workspace)
    assert captured["workspace_pilot_id"] == "PILOT-001"
    assert '"pilot_id": "PILOT-001"' in output
    assert '"pilot_scope": [\n    "supply_and_delivery_only"\n  ]' in output
    assert '"success_criteria": [\n    "submission_ready"\n  ]' in output
    assert '"quote_pack_quality_status": "approval_ready"' in output


def test_approve_workspace_pilot_uses_manifest_pricing_file(tmp_path: Path, monkeypatch, capsys) -> None:
    workspace = tmp_path / "lmcp_pilot_runs"
    pilot_dir = workspace / "PILOT-002"
    (pilot_dir / "rfq_source").mkdir(parents=True, exist_ok=True)
    (pilot_dir / "submission_logs").mkdir(parents=True, exist_ok=True)
    (pilot_dir / "generated_package").mkdir(parents=True, exist_ok=True)
    (pilot_dir / "submission_logs" / "pilot_status.json").write_text(
        json.dumps({"rfq_number": "018_QUOTE_-_Stationary_Extra"}),
        encoding="utf-8",
    )
    pricing_file = pilot_dir / "generated_package" / "pricing.json"
    pricing_file.write_text(json.dumps({"items": []}), encoding="utf-8")
    (pilot_dir / "pilot_manifest.json").write_text(
        json.dumps({"pricing_file": "generated_package/pricing.json"}),
        encoding="utf-8",
    )

    module = _load_module(Path("/Users/cash/Documents/scripts/approve_workspace_pilot.py"), "approve_workspace_pilot")

    captured = {}

    def _fake_approve_manual_pilot(**kwargs):
        captured.update(kwargs)
        return {
            "status": "recorded",
            "reason": "",
            "gate": {"approved": True, "blockers": []},
            "approval_record": {
                "submission_ready": True,
                "manual_approval_recorded": True,
            },
        }

    monkeypatch.setattr(module, "approve_manual_pilot", _fake_approve_manual_pilot)

    exit_code = module.main(
        [
            "--workspace-root",
            str(workspace),
            "--pilot-id",
            "PILOT-002",
            "--confirm-approval",
            "--operator-name",
            "Supervisor",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert captured["tender_root"] == str(pilot_dir / "rfq_source")
    assert captured["tender_id"] == "018_QUOTE_-_Stationary_Extra"
    assert captured["pricing_file"] == str(pricing_file)
    assert captured["confirm_approval"] is True
    assert captured["operator_name"] == "Supervisor"
    assert captured["workspace_root"] == str(workspace)
    assert captured["workspace_pilot_id"] == "PILOT-002"
    assert '"status": "recorded"' in output
    assert '"manual_approval_recorded": true' in output
    assert '"operator_name": "Supervisor"' in output
