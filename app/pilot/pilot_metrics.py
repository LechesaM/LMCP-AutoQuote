from __future__ import annotations

from threading import Lock
from typing import Any, Dict

_LOCK = Lock()
_PILOT_METRICS: Dict[str, Any] = {
    "rfqs_processed": 0,
    "rfqs_refused": 0,
    "successful_workflow_completions": 0,
    "workflow_failures": 0,
    "quote_generation_successes": 0,
    "persistence_failures": 0,
    "recovery_events": 0,
    "manual_interventions": 0,
    "operator_overrides": 0,
    "blocked_workflows": 0,
}


def increment_pilot_metric(name: str, amount: int = 1) -> None:
    with _LOCK:
        _PILOT_METRICS[name] = int(_PILOT_METRICS.get(name, 0)) + int(amount)


def get_pilot_metrics() -> Dict[str, Any]:
    with _LOCK:
        snapshot = dict(_PILOT_METRICS)
    processed = int(snapshot.get("rfqs_processed", 0))
    successes = int(snapshot.get("successful_workflow_completions", 0))
    persistence_failures = int(snapshot.get("persistence_failures", 0))
    manual_interventions = int(snapshot.get("manual_interventions", 0))
    operator_overrides = int(snapshot.get("operator_overrides", 0))
    snapshot["success_rate"] = round((successes / processed), 4) if processed else 0.0
    snapshot["blocked_rate"] = round(int(snapshot.get("blocked_workflows", 0)) / processed, 4) if processed else 0.0
    snapshot["persistence_failure_rate"] = round(persistence_failures / processed, 4) if processed else 0.0
    snapshot["manual_intervention_rate"] = round(manual_interventions / processed, 4) if processed else 0.0
    snapshot["operator_override_rate"] = round(operator_overrides / processed, 4) if processed else 0.0
    snapshot["status"] = "healthy"
    return snapshot


def calculate_success_rate() -> float:
    metrics = get_pilot_metrics()
    return float(metrics.get("success_rate", 0.0))


def calculate_readiness_score() -> float:
    metrics = get_pilot_metrics()
    processed = max(1, int(metrics.get("rfqs_processed", 0)))
    success_rate = float(metrics.get("success_rate", 0.0))
    refusal_handling = 1.0 - min(1.0, int(metrics.get("rfqs_refused", 0)) / processed)
    reliability = 1.0 - min(1.0, int(metrics.get("persistence_failures", 0)) / processed)
    governance = 1.0 - min(1.0, int(metrics.get("workflow_failures", 0)) / processed)
    score = (success_rate * 0.4) + (reliability * 0.25) + (governance * 0.2) + (refusal_handling * 0.15)
    return round(max(0.0, min(1.0, score)) * 100, 2)


def reset_pilot_metrics() -> None:
    with _LOCK:
        for key in list(_PILOT_METRICS):
            _PILOT_METRICS[key] = 0
