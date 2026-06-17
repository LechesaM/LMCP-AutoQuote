from __future__ import annotations

import json
import importlib
from pathlib import Path

from app.core.runtime_paths import get_runtime_paths


def _load_service(monkeypatch, tmp_path: Path, stage: str):
    runtime_dir = tmp_path / "runtime"
    manual_dir = runtime_dir / "manual_production"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    manual_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DIR", str(manual_dir))
    monkeypatch.setenv("LMCP_MANUAL_PRODUCTION_DB_PATH", str(manual_dir / "lmcp_operations.db"))
    monkeypatch.setenv("LMCP_ENABLE_LEGACY_ROUTERS", "0")

    get_runtime_paths.cache_clear()

    import app.services.final_submission_v47_5_service as service

    return importlib.reload(service)


def _write_release_config(tmp_path: Path, payload: dict) -> Path:
    release_dir = tmp_path / "runtime" / "final_submission_v47_5"
    release_dir.mkdir(parents=True, exist_ok=True)
    path = release_dir / "final_submission_release_config.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_v48_release_gate_remains_review_only(monkeypatch, tmp_path: Path) -> None:
    _write_release_config(
        tmp_path,
        {
            "enabled": False,
            "stage": "V48",
        },
    )
    service = _load_service(monkeypatch, tmp_path, "V48")

    gate = service._final_submit_release_gate(
        {
            "submitted_by": "Supervisor",
            "submission_review_status": "review_ready",
            "submission_review_ready": True,
            "approved_pack": True,
            "allow_final_submit": True,
            "blockers": [],
        }
    )

    assert gate["stage"] == "V48"
    assert gate["allowed"] is False
    assert gate["blocked_reason"] == "release_stage_not_v49"


def test_v49_release_gate_requires_named_operator_review_ready_pack(monkeypatch, tmp_path: Path) -> None:
    _write_release_config(
        tmp_path,
        {
            "enabled": True,
            "stage": "V49",
            "requires_named_operator": True,
            "requires_review_ready": True,
            "requires_approved_pack": True,
            "requires_no_blockers": True,
            "requires_explicit_flag": True,
        },
    )
    service = _load_service(monkeypatch, tmp_path, "V49")

    gate = service._final_submit_release_gate(
        {
            "submitted_by": "Supervisor",
            "submission_review_status": "review_ready",
            "submission_review_ready": True,
            "approved_pack": True,
            "allow_final_submit": True,
            "blockers": [],
        }
    )

    assert gate["stage"] == "V49"
    assert gate["allowed"] is True
    assert gate["blocked_reason"] == ""
    assert gate["operator_name"] == "Supervisor"
    assert gate["review_ready"] is True
    assert gate["approved_pack"] is True


def test_v49_release_gate_blocks_on_open_blockers(monkeypatch, tmp_path: Path) -> None:
    _write_release_config(
        tmp_path,
        {
            "enabled": True,
            "stage": "V49",
            "requires_named_operator": True,
            "requires_review_ready": True,
            "requires_approved_pack": True,
            "requires_no_blockers": True,
            "requires_explicit_flag": True,
        },
    )
    service = _load_service(monkeypatch, tmp_path, "V49")

    gate = service._final_submit_release_gate(
        {
            "submitted_by": "Supervisor",
            "submission_review_status": "review_ready",
            "submission_review_ready": True,
            "approved_pack": True,
            "allow_final_submit": True,
            "blockers": [{"code": "missing_proof"}],
        }
    )

    assert gate["stage"] == "V49"
    assert gate["allowed"] is False
    assert gate["blocked_reason"] == "open_blockers_present"


def test_status_summary_reports_release_stage(monkeypatch, tmp_path: Path) -> None:
    _write_release_config(
        tmp_path,
        {
            "enabled": False,
            "stage": "V49",
        },
    )
    service = _load_service(monkeypatch, tmp_path, "V49")

    summary = service.get_final_submission_status(limit=1)["summary"]

    assert summary["final_submit_release_config"]["stage"] == "V49"
    assert summary["final_submit_release_config"]["enabled"] is False


def test_file_backed_release_config_enables_only_when_explicitly_enabled(monkeypatch, tmp_path: Path) -> None:
    _write_release_config(
        tmp_path,
        {
            "enabled": True,
            "stage": "V49",
            "requires_named_operator": True,
            "requires_review_ready": True,
            "requires_approved_pack": True,
            "requires_no_blockers": True,
            "requires_explicit_flag": True,
        },
    )
    service = _load_service(monkeypatch, tmp_path, "V48")

    gate = service._final_submit_release_gate(
        {
            "operator_name": "Supervisor",
            "submission_review_status": "review_ready",
            "submission_review_ready": True,
            "approved_pack": True,
            "allow_final_submit": True,
            "blockers": [],
        }
    )

    assert gate["stage"] == "V49"
    assert gate["release_enabled"] is True
    assert gate["allowed"] is True
