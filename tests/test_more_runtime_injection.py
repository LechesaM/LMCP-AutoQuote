from __future__ import annotations

import os
import json
from pathlib import Path

os.environ.setdefault("LMCP_PROJECT_ROOT", "/Users/cash/Documents")
os.environ.setdefault("LMCP_RUNTIME_DIR", "/Users/cash/Documents/runtime")

from app.services import autonomous_submission_loop_service as loop_service
from app.services import go_live_guard_service as guard_service
from app.services import submission_review_service as review_service


def test_go_live_guard_uses_injected_runtime_dir(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    lock = guard_service.create_submission_lock("RFQ-1", "Q-1", runtime_dir=str(runtime_dir))
    guard_summary = guard_service.get_guard_summary(runtime_dir=str(runtime_dir))
    evaluation = guard_service.evaluate_pipeline_guard({"buyer_rfq_number": "RFQ-1", "quote_number": "Q-1", "runtime_dir": str(runtime_dir)})

    assert lock["buyer_rfq_number"] == "RFQ-1"
    assert guard_summary["summary"]["submission_locks"] == 1
    assert evaluation["allowed"] is False
    assert "Duplicate submission lock exists" in evaluation["blockers"][0]


def test_submission_review_uses_injected_runtime_dir(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    review_service.append_submission_review({"tender_id": "T-1", "tender_root": "root"}, runtime_dir=str(runtime_dir))
    reviews = review_service.list_recent_submission_reviews(runtime_dir=str(runtime_dir))

    assert reviews["total"] == 1
    assert reviews["log_file"] == str(runtime_dir / "manual_production" / "submission_reviews.jsonl")


def test_autonomous_submission_loop_reports_injected_runtime_dir(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime"
    last_run_file = runtime_dir / "submission_scheduler" / "last_run.json"
    last_run_file.parent.mkdir(parents=True, exist_ok=True)
    last_run_file.write_text(json.dumps({"status": "ok", "checked_at": "2026-06-02T20:00:00+00:00"}), encoding="utf-8")

    status = loop_service.get_last_autonomous_submission_loop_run(runtime_dir=str(runtime_dir))
    health = loop_service.get_autonomous_submission_loop_health(runtime_dir=str(runtime_dir))

    assert status["status"] == "ok"
    assert health["last_run_file"] == str(last_run_file)
