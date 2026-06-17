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


def _seed_workspace(tmp_path: Path) -> tuple[Path, Path]:
    workspace = tmp_path / "lmcp_pilot_runs"
    pilot_dir = workspace / "PILOT-001"
    (pilot_dir / "rfq_source").mkdir(parents=True, exist_ok=True)
    (pilot_dir / "submission_logs").mkdir(parents=True, exist_ok=True)
    pricing_file = pilot_dir / "generated_package" / "pricing.json"
    pricing_file.parent.mkdir(parents=True, exist_ok=True)
    pricing_file.write_text(json.dumps({"items": []}), encoding="utf-8")
    (pilot_dir / "submission_logs" / "pilot_status.json").write_text(
        json.dumps({"rfq_number": "REAL-PILOT-001"}),
        encoding="utf-8",
    )
    (pilot_dir / "pilot_manifest.json").write_text(
        json.dumps({"pricing_file": "generated_package/pricing.json"}),
        encoding="utf-8",
    )
    return workspace, pilot_dir


def test_run_supervised_pilot_week_records_approval_and_updates_status(monkeypatch, tmp_path: Path, capsys) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_supervised_pilot_week.py"), "run_supervised_pilot_week")
    workspace, pilot_dir = _seed_workspace(tmp_path)

    captured = {}

    def _fake_run_manual_pilot(**kwargs):
        captured["run_manual_pilot"] = kwargs
        return {
            "status": "warning",
            "quote_pack_quality_status": "approval_ready",
            "approval_blocked": False,
            "pricing_items_unmatched": 0,
            "final_submission_attempted": False,
            "warnings": [],
        }

    def _fake_append_manual_approval(record, runtime_dir=None):
        captured["approval_record"] = record
        return record

    monkeypatch.setattr(module, "run_manual_pilot", _fake_run_manual_pilot)
    monkeypatch.setattr(module.manual_approval_service, "append_manual_approval", _fake_append_manual_approval)

    summary = module.run_supervised_pilot_week(
        workspace_root=str(workspace),
        pilot_id="PILOT-001",
        confirm_approval=True,
        operator_name="Supervisor",
    )
    output = capsys.readouterr().out

    assert summary["manual_approval_recorded"] is True
    assert summary["approval_status"] == "recorded"
    assert summary["next_step"] == "record proof after the live manual submission"
    assert captured["run_manual_pilot"]["tender_root"] == str(pilot_dir / "rfq_source")
    assert captured["run_manual_pilot"]["tender_id"] == "REAL-PILOT-001"
    assert captured["approval_record"]["submission_ready"] is True
    updated_status = json.loads((pilot_dir / "submission_logs" / "pilot_status.json").read_text(encoding="utf-8"))
    assert updated_status["status"] == "approved"
    assert updated_status["submission_ready"] is True
    assert "approval_status" not in output


def test_run_supervised_pilot_week_records_proof_when_requested(monkeypatch, tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_supervised_pilot_week.py"), "run_supervised_pilot_week_proof")
    workspace, pilot_dir = _seed_workspace(tmp_path)
    proof_file = pilot_dir / "proof.pdf"
    proof_file.write_text("proof", encoding="utf-8")

    def _fake_run_manual_pilot(**kwargs):
        return {
            "status": "warning",
            "quote_pack_quality_status": "approval_ready",
            "approval_blocked": False,
            "pricing_items_unmatched": 0,
            "final_submission_attempted": False,
            "warnings": [],
        }

    def _fake_append_manual_approval(record, runtime_dir=None):
        return record

    def _fake_review_submission_pack(**kwargs):
        return {
            "status": "review_ready",
            "submission_review_ready": True,
            "tender_id": kwargs["tender_id"],
            "tender_root": kwargs["tender_root"],
        }

    def _fake_record_manual_submission_proof(**kwargs):
        assert kwargs["portal_name"] == "eTenders"
        assert kwargs["submission_reference"] == "SUB-123"
        assert kwargs["submitted_by"] == "Supervisor"
        return {
            "status": "recorded",
            "manual_submission_recorded": True,
            "submission_review_status": "review_ready",
            "final_submission_attempted": False,
        }

    monkeypatch.setattr(module, "run_manual_pilot", _fake_run_manual_pilot)
    monkeypatch.setattr(module.manual_approval_service, "append_manual_approval", _fake_append_manual_approval)
    monkeypatch.setattr(module.review_submission_pack, "review_submission_pack", _fake_review_submission_pack)
    monkeypatch.setattr(
        module.record_manual_submission_proof,
        "record_manual_submission_proof",
        _fake_record_manual_submission_proof,
    )

    summary = module.run_supervised_pilot_week(
        workspace_root=str(workspace),
        pilot_id="PILOT-001",
        confirm_approval=True,
        operator_name="Supervisor",
        record_proof=True,
        portal_name="eTenders",
        submission_reference="SUB-123",
        proof_file=str(proof_file),
    )

    assert summary["proof_status"] == "recorded"
    assert summary["manual_submission_recorded"] is True
    updated_status = json.loads((pilot_dir / "submission_logs" / "pilot_status.json").read_text(encoding="utf-8"))
    assert updated_status["status"] == "submitted"
    assert updated_status["manual_submission_recorded"] is True


def test_run_supervised_pilot_week_main_rejects_missing_confirmation(monkeypatch, tmp_path: Path, capsys) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_supervised_pilot_week.py"), "run_supervised_pilot_week_main")
    workspace, _ = _seed_workspace(tmp_path)

    monkeypatch.setattr(
        module,
        "run_supervised_pilot_week",
        lambda **kwargs: {
            "pilot_id": "PILOT-001",
            "tender_id": "REAL-PILOT-001",
            "dry_run_status": "warning",
            "quote_pack_quality_status": "approval_ready",
            "approval_blocked": False,
            "submission_ready": False,
            "manual_approval_recorded": False,
            "approval_status": "refused",
            "approval_reason": "confirmation_missing",
            "proof_requested": False,
            "proof_status": "",
            "manual_submission_recorded": False,
            "next_step": "record manual approval first",
            "dry_run_result": {},
            "approval_outcome": {"approval_record": {"manual_approval_recorded": False}},
            "proof_record": None,
            "operator_name": "Supervisor",
            "pricing_file": str(workspace / "PILOT-001" / "generated_package" / "pricing.json"),
        },
    )

    exit_code = module.main(
        [
            "--workspace-root",
            str(workspace),
            "--pilot-id",
            "PILOT-001",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 1
    assert '"approval_reason": "confirmation_missing"' in output


def test_run_supervised_pilot_week_supports_explicit_tender_overrides(monkeypatch, tmp_path: Path) -> None:
    module = _load_module(Path("/Users/cash/Documents/scripts/run_supervised_pilot_week.py"), "run_supervised_pilot_week_overrides")
    workspace = tmp_path / "runtime" / "manual_production"
    pilot_dir = workspace / "PILOT-001"
    tender_root = workspace / "source_bundle_repairs" / "REAL-PILOT-001"
    tender_root.mkdir(parents=True, exist_ok=True)
    (pilot_dir / "submission_logs").mkdir(parents=True, exist_ok=True)
    pricing_file = workspace / "submission_packages" / "REAL-PILOT-001" / "REAL-PILOT-001__manual_pricing_restored_from_governed_quote_pack.json"
    pricing_file.parent.mkdir(parents=True, exist_ok=True)
    pricing_file.write_text(json.dumps({"items": []}), encoding="utf-8")

    captured = {}

    def _fake_run_manual_pilot(**kwargs):
        captured["run_manual_pilot"] = kwargs
        return {
            "status": "warning",
            "quote_pack_quality_status": "approval_ready",
            "approval_blocked": False,
            "pricing_items_unmatched": 0,
            "final_submission_attempted": False,
            "warnings": [],
        }

    monkeypatch.setattr(module, "run_manual_pilot", _fake_run_manual_pilot)
    monkeypatch.setattr(module.manual_approval_service, "append_manual_approval", lambda record, runtime_dir=None: record)

    summary = module.run_supervised_pilot_week(
        workspace_root=str(workspace),
        pilot_id="PILOT-001",
        confirm_approval=True,
        operator_name="Supervisor",
        tender_root=str(tender_root),
        tender_id="REAL-PILOT-001",
        pricing_file=str(pricing_file),
    )

    assert captured["run_manual_pilot"]["tender_root"] == str(tender_root)
    assert captured["run_manual_pilot"]["tender_id"] == "REAL-PILOT-001"
    assert summary["tender_root"] == str(tender_root)
    assert summary["tender_id"] == "REAL-PILOT-001"
