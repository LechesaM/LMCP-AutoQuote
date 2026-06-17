from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


def _ready_detail(tender_id: str) -> dict:
    package_path = f"/tmp/{tender_id}.zip"
    return {
        "status": "ok",
        "tender_id": tender_id,
            "review_ready_bundle": {
                "review_ready": True,
                "submission_ready": True,
            },
            "submission_package": {
            "approval_ready": True,
            "submission_ready": True,
            "package_status": "ready",
            "zip_path": package_path,
            "review_ready_bundle": {
                "review_ready": True,
                "submission_ready": True,
            },
            },
            "submission_execution": {
                "status": "ok",
                "execution_status": "ok",
                "submissionLocked": True,
                "blockers": [],
            },
        }


def test_fresh_live_rfq_backend_smoke_batch_passes_with_ready_refs(monkeypatch, tmp_path: Path) -> None:
    module = importlib.import_module("scripts.fresh_live_rfq_backend_smoke_batch")
    monkeypatch.setenv("LMCP_BACKEND_SMOKE_RFQ_NUMBERS", "REAL-PILOT-001,HTTPPROBE-20260523190924,PAPER")
    monkeypatch.setattr(module, "get_operator_workflow_http_detail", lambda tender_id: {"status": "ok", "tender_id": tender_id})
    monkeypatch.setattr(module, "get_operator_workflow_detail", lambda tender_id: _ready_detail(tender_id))
    monkeypatch.setattr(module, "build_submission_package", lambda detail: _ready_detail(detail["tender_id"])["submission_package"])
    monkeypatch.setattr(module, "build_submission_execution_state", lambda detail: _ready_detail(detail["tender_id"])["submission_execution"])
    for tender_id in ("REAL-PILOT-001", "HTTPPROBE-20260523190924", "PAPER"):
        monkeypatch.setattr(Path, "exists", lambda self, _tender_id=tender_id: True if str(self).endswith(".zip") or str(self).startswith("/tmp/") else Path.exists(self))

    assert module.main([]) == 0


def test_fresh_live_rfq_backend_smoke_batch_fails_on_blocker(monkeypatch) -> None:
    module = importlib.import_module("scripts.fresh_live_rfq_backend_smoke_batch")
    monkeypatch.setenv("LMCP_BACKEND_SMOKE_RFQ_NUMBERS", "PAPER")
    monkeypatch.setattr(module, "get_operator_workflow_http_detail", lambda tender_id: {"status": "ok", "tender_id": tender_id})
    monkeypatch.setattr(
        module,
        "get_operator_workflow_detail",
        lambda tender_id: {
            "status": "ok",
            "tender_id": tender_id,
            "review_ready_bundle": {"review_ready": False, "submission_ready": False},
            "submission_package": {"approval_ready": False, "submission_ready": False, "package_status": "blocked", "zip_path": ""},
            "submission_execution": {"status": "blocked", "execution_status": "blocked", "submissionLocked": False, "blockers": ["approval_ready must be true"]},
        },
    )
    monkeypatch.setattr(module, "build_submission_package", lambda detail: detail["submission_package"])
    monkeypatch.setattr(module, "build_submission_execution_state", lambda detail: detail["submission_execution"])

    with pytest.raises(AssertionError):
        module.main([])
