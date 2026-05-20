from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from app.observability.metrics_registry import get_observability_metrics


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sla_state(value: float, healthy_threshold: float, warning_threshold: float, invert: bool = False) -> str:
    if invert:
        if value >= healthy_threshold:
            return "healthy"
        if value >= warning_threshold:
            return "degraded"
        return "failing"
    if value <= healthy_threshold:
        return "healthy"
    if value <= warning_threshold:
        return "degraded"
    return "failing"


def build_sla_monitoring_report(limit: int = 100) -> Dict[str, Any]:
    payload = get_observability_metrics(limit=limit)
    metrics = payload.get("metrics", {})
    queue_lag = float(metrics.get("queue_lag_minutes", 0.0))
    telemetry_freshness = float(metrics.get("telemetry_freshness_minutes", 0.0))
    backup_age = float(metrics.get("backup_age_days", -1.0))
    source_uptime = float(metrics.get("source_availability", 0.0))
    operator_ack_time = min(120.0, max(0.0, queue_lag / 2.0))
    rfq_latency = min(240.0, max(0.0, queue_lag + float(metrics.get("api_latency_ms", 0.0)) / 1000.0 / 60.0))
    review_completion = min(240.0, max(0.0, queue_lag + float(metrics.get("review_throughput", 0.0)) / 10.0))

    sla_metrics = [
        {"name": "rfq_processing_latency_minutes", "value": round(rfq_latency, 2), "state": _sla_state(rfq_latency, 15.0, 30.0)},
        {"name": "review_completion_time_minutes", "value": round(review_completion, 2), "state": _sla_state(review_completion, 20.0, 45.0)},
        {"name": "queue_wait_time_minutes", "value": round(queue_lag, 2), "state": _sla_state(queue_lag, 15.0, 30.0)},
        {"name": "source_uptime_percent", "value": round(source_uptime, 2), "state": _sla_state(source_uptime, 99.0, 95.0, invert=True)},
        {"name": "operator_acknowledgement_time_minutes", "value": round(operator_ack_time, 2), "state": _sla_state(operator_ack_time, 15.0, 30.0)},
        {"name": "backup_freshness_days", "value": round(backup_age, 2), "state": _sla_state(backup_age, 1.0, 3.0)},
        {"name": "telemetry_freshness_minutes", "value": round(telemetry_freshness, 2), "state": _sla_state(telemetry_freshness, 5.0, 15.0)},
    ]
    breached = [metric for metric in sla_metrics if metric["state"] == "failing"]
    warnings = [metric for metric in sla_metrics if metric["state"] == "degraded"]
    status = "healthy"
    if breached:
        status = "failing"
    elif warnings:
        status = "degraded"
    stability_score = 100.0
    stability_score -= len(breached) * 12.0
    stability_score -= len(warnings) * 5.0
    stability_score -= min(20.0, max(0.0, queue_lag))
    stability_score -= min(15.0, max(0.0, telemetry_freshness))
    stability_score = max(0.0, stability_score)
    return {
        "status": status,
        "generated_at": _now_iso(),
        "data_source": payload.get("data_source", "fallback"),
        "stability_score": round(stability_score, 2),
        "sla_metrics": sla_metrics,
        "breached_metrics": breached,
        "warning_metrics": warnings,
        "runtime_stability": {
            "status": status,
            "stability_score": round(stability_score, 2),
        },
        "summary": {
            "healthy": len([metric for metric in sla_metrics if metric["state"] == "healthy"]),
            "degraded": len(warnings),
            "failing": len(breached),
        },
    }
