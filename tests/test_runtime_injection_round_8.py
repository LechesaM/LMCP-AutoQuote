from __future__ import annotations

import asyncio
import os
from pathlib import Path

os.environ.setdefault("LMCP_PROJECT_ROOT", "/Users/cash/Documents")
os.environ.setdefault("LMCP_RUNTIME_DIR", "/Users/cash/Documents/runtime")

from app.services import decision_intelligence_service as decision
from app.services import operator_action_service as actions


def test_operator_action_service_uses_injected_runtime_dir(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"

    async def run() -> None:
        await actions.record_operator_action(
            "force_quote",
            {"buyer_rfq_number": "RFQ-1", "reason": "testing"},
            runtime_dir=str(runtime_dir),
        )

    asyncio.run(run())
    summary = actions.get_operator_action_summary(runtime_dir=str(runtime_dir))

    assert summary["summary"]["total_actions"] == 1
    assert summary["history_file"] == str(runtime_dir / "operator_actions" / "operator_action_history.json")
    assert (runtime_dir / "operator_actions" / "operator_action_history.json").exists()


def test_decision_intelligence_uses_injected_runtime_dir(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"

    async def run() -> None:
        await decision.score_and_publish(
            {
                "buyer_rfq_number": "RFQ-2",
                "title": "Supply and delivery of stationery",
                "submission_method": "email",
                "estimated_profit": 35000,
                "estimated_margin_percent": 30,
                "province": "Gauteng",
            },
            runtime_dir=str(runtime_dir),
        )

    asyncio.run(run())
    summary = decision.get_decision_summary(runtime_dir=str(runtime_dir))

    assert summary["summary"]["total_scored"] == 1
    assert summary["history_file"] == str(runtime_dir / "decision_intelligence" / "decision_history.json")
    assert (runtime_dir / "decision_intelligence" / "decision_history.json").exists()
