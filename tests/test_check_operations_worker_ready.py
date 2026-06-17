from __future__ import annotations

import importlib


def test_operations_worker_ready_probe_detects_queue(monkeypatch) -> None:
    module = importlib.import_module("scripts.check_operations_worker_ready")

    class FakeInspector:
        def ping(self):
            return {"worker-a@host": {"ok": "pong"}}

        def active_queues(self):
            return {
                "worker-a@host": [
                    {"name": "default"},
                    {"name": "operations_queue"},
                ]
            }

    monkeypatch.setattr(module.celery_app.control, "inspect", lambda timeout=1.0: FakeInspector())

    payload = module.wait_for_queue_ready(queue_name="operations_queue", timeout_seconds=0.1, poll_interval_seconds=0.01)

    assert payload["ready"] is True
    assert payload["status"] == "healthy"
    assert payload["queue_workers"] == ["worker-a@host"]


def test_operations_worker_ready_probe_fails_without_queue(monkeypatch) -> None:
    module = importlib.import_module("scripts.check_operations_worker_ready")

    class FakeInspector:
        def ping(self):
            return {"worker-a@host": {"ok": "pong"}}

        def active_queues(self):
            return {"worker-a@host": [{"name": "default"}]}

    monkeypatch.setattr(module.celery_app.control, "inspect", lambda timeout=1.0: FakeInspector())

    payload = module.wait_for_queue_ready(queue_name="operations_queue", timeout_seconds=0.05, poll_interval_seconds=0.01)

    assert payload["ready"] is False
    assert payload["status"] == "unhealthy"

