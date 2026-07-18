from __future__ import annotations

from typing import Any, Dict

from app.services.rfq_lifecycle_service import RfqLifecycleService


class _InMemoryStore:
    state_file = "memory://rfqs.json"

    def __init__(self) -> None:
        self.analytics_payload = None

    def read(self) -> Dict[str, Any]:
        return {
            "items": {},
            "throughput": {},
            "scale_simulation": {},
        }

    def read_audit(self) -> Dict[str, Any]:
        return {"events": []}

    def write_analytics(self, payload: Dict[str, Any]) -> None:
        self.analytics_payload = payload


def _prepare_service(monkeypatch, queue_metrics):
    service = RfqLifecycleService()
    service.store = _InMemoryStore()
    calls = []

    def fake_queue_analytics(items, queue, throughput):
        calls.append(
            {
                "items": items,
                "queue": queue,
                "throughput": throughput,
            }
        )
        return queue_metrics

    monkeypatch.setattr(service, "_queue_analytics", fake_queue_analytics)
    monkeypatch.setattr(
        service,
        "mission_control_summary",
        lambda: {"lifecycle_health_score": 100.0},
    )
    monkeypatch.setattr(service, "_source_reliability", lambda items: 100.0)
    monkeypatch.setattr(
        service,
        "submission_safety_guard",
        lambda: {
            "manual_submission_required": True,
            "autonomous_submission": False,
        },
    )

    return service, calls


def test_analytics_initializes_queue_metrics(monkeypatch):
    service, calls = _prepare_service(
        monkeypatch,
        {
            "queue_wait_time": {},
            "task_processing_rate": 0.0,
            "saturation_warnings": [],
        },
    )

    result = service.analytics()

    assert len(calls) == 1
    assert calls[0]["items"] == []
    assert calls[0]["throughput"] == {}
    assert result["status"] == "ok"
    assert result["queue_wait_times"] == {}
    assert result["queue_drain_rate"] == 0.0
    assert result["worker_saturation_warnings"] == []


def test_analytics_accepts_plural_queue_wait_times(monkeypatch):
    service, _ = _prepare_service(
        monkeypatch,
        {
            "queue_wait_times": {"READY_FOR_REVIEW": 12.5},
            "task_processing_rate": 0.0,
            "saturation_warnings": [],
        },
    )

    result = service.analytics()

    assert result["queue_wait_times"] == {"READY_FOR_REVIEW": 12.5}
