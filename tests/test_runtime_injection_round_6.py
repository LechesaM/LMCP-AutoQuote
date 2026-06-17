from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("LMCP_PROJECT_ROOT", "/Users/cash/Documents")
os.environ.setdefault("LMCP_RUNTIME_DIR", "/Users/cash/Documents/runtime")

from app.services import real_profit_pricing_service as pricing
from app.services import safe_autonomous_scheduler_service as scheduler


def test_real_profit_pricing_uses_injected_runtime_dir(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    result = pricing.enrich_with_real_profit_pricing(
        {
            "buyer_rfq_number": "RFQ-100",
            "title": "Supply and delivery of stationery",
            "line_items": [{"quantity": 1, "unit_price": 1000}],
        },
        runtime_dir=str(runtime_dir),
    )
    status = pricing.get_real_profit_pricing_status(runtime_dir=str(runtime_dir))

    assert result["status"] == "ok"
    assert status["files"]["runtime_dir"] == str(runtime_dir / "real_profit_pricing")
    assert (runtime_dir / "real_profit_pricing" / "last_pricing.json").exists()


def test_safe_scheduler_uses_injected_runtime_dir(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    state = scheduler.update_scheduler_state({"enabled": False}, runtime_dir=str(runtime_dir))
    status = scheduler.get_safe_scheduler_status(runtime_dir=str(runtime_dir))

    assert state["enabled"] is False
    assert status["files"]["state"] == str(runtime_dir / "safe_autonomous_scheduler" / "state.json")
    assert status["files"]["history"] == str(runtime_dir / "safe_autonomous_scheduler" / "history.json")
    assert status["files"]["last_run"] == str(runtime_dir / "safe_autonomous_scheduler" / "last_run.json")
