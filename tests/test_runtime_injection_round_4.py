from __future__ import annotations

import asyncio
import os
from pathlib import Path

os.environ.setdefault("LMCP_PROJECT_ROOT", "/Users/cash/Documents")
os.environ.setdefault("LMCP_RUNTIME_DIR", "/Users/cash/Documents/runtime")

from app.services import audit_trail_service as audit
from app.services import manual_approval_service as approvals
from app.services import production_lock_service as prod_lock


def test_manual_approval_uses_injected_runtime_dir(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    record = approvals.append_manual_approval({"approval": True}, runtime_dir=str(runtime_dir))
    listing = approvals.list_recent_manual_approvals(runtime_dir=str(runtime_dir))

    assert record["approval"] is True
    assert listing["log_file"] == str(runtime_dir / "manual_production" / "approvals.jsonl")
    assert (runtime_dir / "manual_production" / "approvals.jsonl").exists()


def test_audit_trail_uses_injected_runtime_dir(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    result = asyncio.run(
        audit.record_audit_event(
            "runtime_test",
            payload={"ok": True},
            runtime_dir=str(runtime_dir),
        )
    )
    events = audit.get_audit_events(runtime_dir=str(runtime_dir))
    summary = audit.get_audit_summary(runtime_dir=str(runtime_dir))

    assert result["event_type"] == "runtime_test"
    assert events["history_file"] == str(runtime_dir / "audit_trail" / "audit_events.json")
    assert summary["history_file"] == str(runtime_dir / "audit_trail" / "audit_events.json")
    assert (runtime_dir / "audit_trail" / "audit_events.json").exists()


def test_production_lock_uses_injected_runtime_dir(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    decision = prod_lock.evaluate_production_lock({"estimated_profit": 50000, "estimated_margin_percent": 50}, runtime_dir=str(runtime_dir))
    status = prod_lock.get_production_lock_status(runtime_dir=str(runtime_dir))

    assert decision["allowed"] is True
    assert status["files"]["policy"] == str(runtime_dir / "production_lock" / "production_policy.json")
    assert status["files"]["history"] == str(runtime_dir / "production_lock" / "decision_history.json")
