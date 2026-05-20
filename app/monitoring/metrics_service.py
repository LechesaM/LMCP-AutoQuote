from __future__ import annotations

from threading import Lock
from typing import Any, Dict

from app.domain.base import StrictBaseModel, utc_now

_LOCK = Lock()
_METRICS: Dict[str, int] = {
    "rfqs_discovered": 0,
    "rfqs_evaluated": 0,
    "rfqs_refused": 0,
    "quote_packs_generated": 0,
    "approvals_recorded": 0,
    "reviews_recorded": 0,
    "proofs_recorded": 0,
    "archived_workflows": 0,
    "workflow_failures": 0,
    "persistence_failures": 0,
    "audit_failures": 0,
    "auth_failures": 0,
    "rate_limit_events": 0,
    "api_latency_ms": 0,
    "telemetry_freshness_minutes": 0,
}


class MetricsSnapshot(StrictBaseModel):
    metrics: Dict[str, int]
    updated_at: Any = None


def increment_metric(metric_name: str, amount: int = 1) -> None:
    with _LOCK:
        _METRICS[metric_name] = int(_METRICS.get(metric_name, 0)) + int(amount)


def get_metrics_snapshot() -> Dict[str, Any]:
    with _LOCK:
        snapshot = dict(_METRICS)
    return MetricsSnapshot(metrics=snapshot, updated_at=utc_now()).to_jsonable_dict()


def reset_test_metrics() -> None:
    with _LOCK:
        for key in list(_METRICS):
            _METRICS[key] = 0
