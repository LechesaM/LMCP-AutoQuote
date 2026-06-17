from __future__ import annotations

from app import tasks_api


def test_source_by_source_live_smoke_api_uses_helper(monkeypatch) -> None:
    captured = {}

    def fake_helper(**kwargs):
        captured.update(kwargs)
        return {"status": "ok", "source_count": 1, "results": [{"status": "ok"}]}

    monkeypatch.setattr(tasks_api, "run_source_by_source_live_smoke_helper", fake_helper)

    response = tasks_api.run_source_by_source_live_smoke_now(
        source_file="/tmp/sources.json",
        source_name="Portal",
        source_group="etenders",
        limit=1,
        runtime_dir="/tmp/runtime",
        source_timeout_seconds=3,
        playwright_timeout_ms=5000,
        fail_fast=True,
        emit_progress=True,
    )

    assert response["status"] == "ok"
    assert response["task_name"] == "run_source_by_source_live_smoke"
    assert captured["source_file"] == "/tmp/sources.json"
    assert captured["source_name"] == "Portal"
    assert captured["source_group"] == "etenders"
    assert captured["limit"] == 1
    assert captured["runtime_dir"] == "/tmp/runtime"
    assert captured["source_timeout_seconds"] == 3
    assert captured["playwright_timeout_ms"] == 5000
    assert captured["fail_fast"] is True
    assert captured["emit_progress"] is True
