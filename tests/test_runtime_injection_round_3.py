from __future__ import annotations

import asyncio
import os
from pathlib import Path

os.environ.setdefault("LMCP_PROJECT_ROOT", "/Users/cash/Documents")
os.environ.setdefault("LMCP_RUNTIME_DIR", "/Users/cash/Documents/runtime")

from app.services import portal_upload_service as portal_upload
from app.services import submission_analytics_service as analytics
from app.services import submission_history_service as history


def test_submission_history_uses_injected_runtime_dir(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    record = history.log_submission_event(
        {
            "buyer_name": "Acme",
            "buyer_rfq_number": "RFQ-42",
            "quote_number": "Q-42",
            "status": "submitted",
            "submission_method": "email",
            "runtime_dir": str(runtime_dir),
        },
        runtime_dir=str(runtime_dir),
    )
    summary = history.get_submission_summary(runtime_dir=str(runtime_dir))

    assert record["buyer_rfq_number"] == "RFQ-42"
    assert summary["history_file"] == str(runtime_dir / "submission_history" / "submission_history.json")
    assert (runtime_dir / "submission_history" / "submission_history.json").exists()


def test_submission_analytics_uses_injected_runtime_dir(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    history.log_submission_event(
        {
            "buyer_name": "Acme",
            "buyer_rfq_number": "RFQ-84",
            "quote_number": "Q-84",
            "status": "submitted",
            "submission_method": "email",
            "raw_result": {"estimated_revenue": 1000, "estimated_cost": 600, "estimated_profit": 400},
        },
        runtime_dir=str(runtime_dir),
    )
    success = analytics.get_submission_success_tracking(runtime_dir=str(runtime_dir))
    profit = analytics.get_submission_profit_tracking(runtime_dir=str(runtime_dir))
    summary = analytics.get_submission_success_and_profit_summary(runtime_dir=str(runtime_dir))

    assert success["history_file"] == str(runtime_dir / "submission_history" / "submission_history.json")
    assert profit["history_file"] == str(runtime_dir / "submission_history" / "submission_history.json")
    assert summary["success_tracking"]["history_file"] == str(runtime_dir / "submission_history" / "submission_history.json")


def test_portal_upload_uses_injected_runtime_dir(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    result = asyncio.run(portal_upload.upload_submission_documents({"runtime_dir": str(runtime_dir)}))
    status = portal_upload.get_portal_upload_status(runtime_dir=str(runtime_dir))
    discovery = portal_upload.find_latest_generated_quote(runtime_dir=str(runtime_dir))

    assert result["status"] == "assisted_required"
    assert status["files"]["runtime_dir"] == str(runtime_dir / "portal_uploads")
    assert discovery["status"] in {"not_found", "ok"}
    assert (runtime_dir / "portal_uploads" / "portal_upload_history.json").exists()
