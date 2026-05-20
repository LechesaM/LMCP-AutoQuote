from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _panel(title: str, metric: str, description: str, threshold: float | None = None) -> Dict[str, Any]:
    panel: Dict[str, Any] = {
        "title": title,
        "metric": metric,
        "description": description,
        "type": "timeseries",
    }
    if threshold is not None:
        panel["threshold"] = threshold
    return panel


def build_grafana_dashboard_bundle(limit: int = 100) -> Dict[str, Any]:
    dashboards: List[Dict[str, Any]] = [
        {
            "uid": "runtime-health",
            "title": "Runtime Health",
            "tags": ["lmcp", "runtime", "health"],
            "panels": [
                _panel("Runtime Uptime", "uptime_percent", "Runtime availability trend.", 99.0),
                _panel("Telemetry Freshness", "telemetry_freshness_minutes", "Freshness window for operational telemetry.", 15.0),
                _panel("API Latency", "api_latency_ms", "Read-only API latency.", 250.0),
            ],
        },
        {
            "uid": "operator-throughput",
            "title": "Operator Throughput",
            "tags": ["lmcp", "operators", "queue"],
            "panels": [
                _panel("RFQs Harvested", "rfqs_harvested", "Harvest throughput."),
                _panel("RFQs Qualified", "rfqs_qualified", "Qualification throughput."),
                _panel("Review Throughput", "review_throughput", "Daily review throughput."),
            ],
        },
        {
            "uid": "source-reliability",
            "title": "Source Reliability",
            "tags": ["lmcp", "sources"],
            "panels": [
                _panel("Source Availability", "source_availability", "Healthy source percentage.", 95.0),
                _panel("Parser Failure Rate", "parser_failure_rate", "Parser failure rate.", 0.15),
                _panel("Worker Health", "worker_health", "Worker heartbeat health."),
            ],
        },
        {
            "uid": "queue-durability",
            "title": "Queue Durability",
            "tags": ["lmcp", "queue"],
            "panels": [
                _panel("Queue Lag", "queue_lag_minutes", "Queue wait time in minutes.", 30.0),
                _panel("DLQ Count", "dlq_count", "Dead letter queue depth."),
                _panel("Queue Backend Ready", "queue_backend_ready", "Redis-ready queue availability."),
            ],
        },
        {
            "uid": "persistence-health",
            "title": "Persistence Health",
            "tags": ["lmcp", "persistence"],
            "panels": [
                _panel("Backup Age", "backup_age_days", "Latest backup age in days.", 3.0),
                _panel("Persistence Failures", "persistence_failures", "Persistence failures recorded."),
                _panel("Audit Failures", "audit_failures", "Audit persistence issues."),
            ],
        },
        {
            "uid": "incident-trends",
            "title": "Incident Trends",
            "tags": ["lmcp", "incidents"],
            "panels": [
                _panel("Runtime Alerts", "runtime_alerts", "Alert frequency trend."),
                _panel("Incident Count", "incident_count", "Incident volume."),
                _panel("Worker Stale Count", "worker_stale_count", "Stale worker heartbeats."),
            ],
        },
        {
            "uid": "sla-metrics",
            "title": "SLA Metrics",
            "tags": ["lmcp", "sla"],
            "panels": [
                _panel("Queue Lag", "queue_lag_minutes", "Queue wait SLA."),
                _panel("Telemetry Freshness", "telemetry_freshness_minutes", "Telemetry freshness SLA."),
                _panel("Backup Freshness", "backup_age_days", "Backup freshness SLA."),
            ],
        },
    ]
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": "runtime",
        "dashboards": dashboards,
        "count": len(dashboards),
    }
