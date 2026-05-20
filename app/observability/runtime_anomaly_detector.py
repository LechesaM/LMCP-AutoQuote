from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.operations.runtime_metrics import get_runtime_metrics, get_runtime_snapshots
from app.observability.metrics_registry import get_observability_metrics


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _anomaly(anomaly_type: str, severity: str, message: str, *, affected_systems: List[str] | None = None, evidence: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return {
        "anomaly_id": f"anomaly-{datetime.now(timezone.utc).timestamp()}",
        "type": anomaly_type,
        "severity": severity,
        "message": message,
        "affected_systems": affected_systems or [],
        "evidence": evidence or {},
        "created_at": _now_iso(),
        "advisory_only": True,
    }


def build_runtime_anomaly_report(limit: int = 100) -> Dict[str, Any]:
    current = get_observability_metrics(limit=limit)
    runtime = get_runtime_metrics(limit=limit)
    snapshots = get_runtime_snapshots(limit=limit).get("snapshots", [])
    previous = snapshots[-2].get("payload", {}) if len(snapshots) >= 2 and isinstance(snapshots[-2], dict) else {}
    current_metrics = current.get("metrics", {})
    previous_metrics = previous.get("metrics", {}) if isinstance(previous, dict) else {}
    anomalies: List[Dict[str, Any]] = []

    queue_lag = float(current_metrics.get("queue_lag_minutes", 0.0))
    previous_queue_lag = float(previous_metrics.get("queue_lag", previous_metrics.get("queue_lag_minutes", 0.0)) or 0.0)
    if queue_lag >= max(45.0, previous_queue_lag * 1.5):
        anomalies.append(_anomaly("queue_spike", "critical", "Queue lag spiked beyond the advisory threshold.", affected_systems=["queue", "operator"], evidence={"queue_lag_minutes": queue_lag, "previous_queue_lag_minutes": previous_queue_lag}))

    rfqs_harvested = float(current_metrics.get("rfqs_harvested", 0.0))
    if previous_metrics and rfqs_harvested <= max(1.0, float(previous_metrics.get("rfqs_harvested_per_hour", 0.0)) * 0.5):
        anomalies.append(_anomaly("rfq_dropoff", "warning", "RFQ harvest rate dropped significantly.", affected_systems=["harvest", "telemetry"], evidence={"rfqs_harvested": rfqs_harvested}))

    parser_failure_rate = float(current_metrics.get("parser_failure_rate", 0.0))
    if parser_failure_rate > 0.2:
        anomalies.append(_anomaly("parser_failure_spike", "critical", "Parser failures exceed the safe threshold.", affected_systems=["parser", "source"], evidence={"parser_failure_rate": parser_failure_rate}))

    auth_failures = int(current_metrics.get("auth_failures", 0))
    if auth_failures > 0:
        anomalies.append(_anomaly("auth_failure_anomaly", "warning", "Authentication failures were observed.", affected_systems=["auth"], evidence={"auth_failures": auth_failures}))

    freshness = float(current_metrics.get("telemetry_freshness_minutes", 0.0))
    if freshness > 15:
        anomalies.append(_anomaly("stale_telemetry", "warning", "Telemetry freshness exceeded the advisory threshold.", affected_systems=["telemetry"], evidence={"telemetry_freshness_minutes": freshness}))

    stale_workers = int(current_metrics.get("worker_health", 1.0) == 0.0)
    if stale_workers:
        anomalies.append(_anomaly("worker_heartbeat", "warning", "One or more worker heartbeats appear stale.", affected_systems=["workers"], evidence={"worker_health": current_metrics.get("worker_health", 0)}))

    source_availability = float(current_metrics.get("source_availability", 0.0))
    if source_availability < 80.0:
        anomalies.append(_anomaly("source_reliability", "warning", "Source availability is below the preferred threshold.", affected_systems=["sources"], evidence={"source_availability": source_availability}))

    status = "healthy"
    if any(item["severity"] == "critical" for item in anomalies):
        status = "failing"
    elif anomalies:
        status = "degraded"

    severity_counts = Counter(item["severity"] for item in anomalies)
    return {
        "status": status,
        "generated_at": _now_iso(),
        "data_source": current.get("data_source", runtime.get("data_source", "fallback")),
        "anomalies": anomalies[: max(1, int(limit or 100))],
        "anomaly_count": len(anomalies),
        "severity_counts": dict(severity_counts),
        "advisory_only": True,
    }
