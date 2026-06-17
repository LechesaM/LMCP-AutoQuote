from __future__ import annotations

import importlib
import json
from pathlib import Path

from app.core.runtime_paths import get_runtime_paths


def test_daily_supervised_production_ritual_writes_report_and_history(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(tmp_path / "runtime"))
    get_runtime_paths.cache_clear()

    module = importlib.import_module("scripts.daily_supervised_production_ritual")

    events = []
    monkeypatch.setattr(module, "append_audit_event", lambda **kwargs: events.append(kwargs) or {"status": "ok"})
    async def fake_safe_cycle(**kwargs):
        return {
            "status": "ok",
            "items": [
                {"buyer_rfq_number": "PAPER", "final_status": "submitted"},
                {"buyer_rfq_number": "RFQ-2", "final_status": "blocked_by_production_lock"},
            ],
        }

    monkeypatch.setattr(module, "run_safe_autonomous_cycle", fake_safe_cycle)
    monkeypatch.setattr(module, "run_autonomous_submission_loop", lambda **kwargs: {"status": "ok", "total_processed": 1})
    monkeypatch.setattr(module, "enrich_submission_history_with_proof_paths", lambda: {"status": "ok", "updated": 1})
    monkeypatch.setattr(module, "get_submission_summary", lambda: {"submitted": 1, "failed": 0, "total": 1})
    monkeypatch.setattr(module, "get_submission_success_tracking", lambda: {"status": "ok", "total": 1})
    monkeypatch.setattr(module, "get_submission_profit_tracking", lambda submitted_only=True: {"gross_margin": 42.0, "margin_rate": 0.35})
    recon_calls = []
    monkeypatch.setattr(module, "reconcile_submission_execution", lambda detail: recon_calls.append(detail) or {"status": "ok", "reconciled": True})

    assert module.main(["--limit", "2", "--max-total", "5", "--max-submissions", "2"]) == 0

    report_path = tmp_path / "runtime" / "manual_production" / "daily_supervised_production_ritual.json"
    history_path = tmp_path / "runtime" / "manual_production" / "daily_supervised_production_ritual_history.jsonl"
    assert report_path.exists()
    assert history_path.exists()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "ok"
    assert report["submission_count"] == 1
    assert report["daily_gross_margin"] == 42.0
    assert report["daily_margin_rate"] == 0.35
    assert len(recon_calls) == 2
    assert events[0]["event_type"] == "daily_supervised_production_ritual_started"
    assert events[-1]["event_type"] == "daily_supervised_production_ritual_completed"


def test_daily_supervised_production_ritual_requires_confirm_submit(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(tmp_path / "runtime"))
    get_runtime_paths.cache_clear()

    module = importlib.import_module("scripts.daily_supervised_production_ritual")

    try:
        module.main(["--enable-submit"])
        raise AssertionError("Expected confirm-submit guard to raise SystemExit")
    except SystemExit as exc:
        assert "--confirm-submit is required" in str(exc)


def test_daily_supervised_production_ritual_min_submitted_guard(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LMCP_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("LMCP_RUNTIME_DIR", str(tmp_path / "runtime"))
    get_runtime_paths.cache_clear()

    module = importlib.import_module("scripts.daily_supervised_production_ritual")

    monkeypatch.setattr(module, "append_audit_event", lambda **kwargs: {"status": "ok"})
    async def fake_safe_cycle(**kwargs):
        return {"status": "ok", "items": []}

    monkeypatch.setattr(module, "run_safe_autonomous_cycle", fake_safe_cycle)
    monkeypatch.setattr(module, "run_autonomous_submission_loop", lambda **kwargs: {"status": "ok", "total_processed": 0})
    monkeypatch.setattr(module, "enrich_submission_history_with_proof_paths", lambda: {"status": "ok"})
    monkeypatch.setattr(module, "get_submission_summary", lambda: {"submitted": 0, "failed": 0, "total": 0})
    monkeypatch.setattr(module, "get_submission_success_tracking", lambda: {"status": "ok", "total": 0})
    monkeypatch.setattr(module, "get_submission_profit_tracking", lambda submitted_only=True: {"gross_margin": 0.0, "margin_rate": 0.0})
    monkeypatch.setattr(module, "reconcile_submission_execution", lambda detail: {"status": "ok"})

    try:
        module.main(["--min-submitted", "1"])
        raise AssertionError("Expected minimum submitted guard to raise SystemExit")
    except SystemExit as exc:
        assert "below minimum required" in str(exc)
