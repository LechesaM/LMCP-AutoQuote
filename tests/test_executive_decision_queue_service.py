from __future__ import annotations

import importlib


def test_executive_decision_queue_service_returns_governed_snapshot_and_history(tmp_path) -> None:
    module = importlib.import_module("app.services.executive_decision_queue_service")
    service = module.ExecutiveDecisionQueueService(runtime_dir=tmp_path / "runtime" / "staging" / "executive-governance")

    latest = service.latest_executive_decision_queue()
    history = service.executive_decision_queue_history(limit=5)

    assert latest["status"] in {"ok", "watch"}
    assert latest["latest_executive_decision_queue"]["executive_decision_queue_ready"] is True
    assert latest["latest_executive_decision_queue"]["queue_items"]
    assert history["count"] >= 1
