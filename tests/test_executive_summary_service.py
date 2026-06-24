from __future__ import annotations

import importlib


def test_executive_summary_service_returns_governed_snapshot_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.executive_summary_service")
    service = module.ExecutiveSummaryService(runtime_dir=tmp_path / "runtime" / "staging" / "executive-governance")

    latest = service.latest_executive_summary()
    history = service.executive_summary_history(limit=5)

    assert latest["status"] in {"ok", "watch"}
    assert latest["latest_executive_summary"]["executive_summary_ready"] is True
    assert latest["latest_executive_summary"]["governance_rules"]["executive_human_approval_required"] is True
    assert history["count"] >= 1
