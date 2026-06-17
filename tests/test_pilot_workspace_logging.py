from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_script_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_append_workspace_log_entry_writes_markdown(tmp_path: Path) -> None:
    from app.services.pilot_run_log_service import append_workspace_log_entry

    workspace_root = tmp_path / "lmcp_pilot_runs"
    log_path = append_workspace_log_entry(
        workspace_root,
        "PILOT-001",
        "Import",
        fields={"Stage": "rfq intake", "Status": "completed", "File Count": 2},
        notes=["RFQ captured correctly."],
    )

    path = Path(log_path)
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "## Import" in content
    assert "- Pilot ID: PILOT-001" in content
    assert "- Stage: rfq intake" in content
    assert "- Status: completed" in content
    assert "- File Count: 2" in content
    assert "RFQ captured correctly." in content


def test_append_workspace_log_entry_preserves_false_and_zero(tmp_path: Path) -> None:
    from app.services.pilot_run_log_service import append_workspace_log_entry

    workspace_root = tmp_path / "lmcp_pilot_runs"
    log_path = append_workspace_log_entry(
        workspace_root,
        "PILOT-002",
        "Outcome",
        fields={"Approval Blocked": False, "Submission Ready": False, "Pricing Items Matched": 0},
    )

    content = Path(log_path).read_text(encoding="utf-8")
    assert "Approval Blocked: False" in content
    assert "Submission Ready: False" in content
    assert "Pricing Items Matched: 0" in content


def test_run_manual_pilot_appends_workspace_log(monkeypatch, tmp_path: Path) -> None:
    module_path = Path("/Users/cash/Documents/scripts/run_manual_pilot.py")
    module = _load_script_module(module_path, "run_manual_pilot")

    class _Pipeline:
        def run(self, **kwargs):
            return {
                "status": "warning",
                "quote_pack_quality_status": "approval_ready",
                "approval_blocked": False,
                "submission_ready": True,
                "quote_pack_generated": True,
                "submission_pack_generated": True,
                "pricing_items_matched": 4,
                "pricing_items_unmatched": 0,
                "warnings": ["manual review complete"],
                "message": "",
                "pipeline_stages": [
                    {
                        "key": "tender_pack_intake",
                        "name": "tender pack intake",
                        "status": "completed",
                        "details": {"tender_root": kwargs["tender_root"], "file_count": 3},
                    },
                    {
                        "key": "quote_pack_quality_assessment",
                        "name": "quote pack quality assessment",
                        "status": "completed",
                        "details": {"quote_pack_quality_status": "approval_ready", "approval_blocked": False},
                    },
                ],
            }

    monkeypatch.setattr(module, "TenderSubmissionPipeline", _Pipeline)

    result = module.run_manual_pilot(
        tender_root=str(tmp_path / "tender"),
        tender_id="REAL-PILOT-001",
        workspace_root=str(tmp_path / "lmcp_pilot_runs"),
        workspace_pilot_id="PILOT-001",
    )

    assert result["status"] == "warning"
    log_path = tmp_path / "lmcp_pilot_runs" / "PILOT-001" / "submission_logs" / "live_run_log.md"
    content = log_path.read_text(encoding="utf-8")
    assert "## Import" in content
    assert "## Review" in content
    assert "## Outcome" in content
    assert "tender pack intake" in content
    assert "quote pack quality assessment" in content
    assert "Submission Ready: True" in content
