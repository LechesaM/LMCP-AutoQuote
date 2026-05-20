from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from app.core.runtime_config import get_runtime_config
from app.operations.health_snapshots import get_health_snapshots
from app.operations.runtime_metrics import get_runtime_metrics
from app.orchestration.redis_config import get_redis_config, redis_connection_ready
from app.persistence.backup_scheduler import get_backup_status
from app.persistence.persistence_health import validate_persistence_health


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _alert(alert_type: str, severity: str, title: str, message: str, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return {
        "alert_id": f"alert-{datetime.now(timezone.utc).timestamp()}",
        "type": alert_type,
        "severity": severity,
        "title": title,
        "message": message,
        "created_at": _now_iso(),
        "acknowledged": False,
        "details": details or {},
    }


def get_runtime_alerts(limit: int = 100) -> Dict[str, Any]:
    snapshot = get_health_snapshots(limit=limit)
    latest = snapshot.get("snapshots", [])[-1] if snapshot.get("snapshots") else {}
    source_summary = latest.get("source_summary", {})
    queue_summary = latest.get("queue_summary", {})
    metrics = latest.get("metrics", {}).get("metrics", {})
    runtime_metrics = get_runtime_metrics(limit=limit)
    backup_status = get_backup_status()
    persistence_health = validate_persistence_health()
    redis_config = get_redis_config()
    runtime = get_runtime_config()

    alerts: List[Dict[str, Any]] = []
    if source_summary.get("failing_sources", 0):
        alerts.append(_alert("source_outage", "critical", "Source outage", "One or more sources are failing.", {"source_summary": source_summary}))
    if queue_summary.get("blocked_jobs", 0):
        alerts.append(_alert("queue_overload", "critical", "Queue overload", "Blocked jobs detected in the queue.", {"queue_summary": queue_summary}))
    if metrics.get("telemetry_freshness_minutes", 0) > 15:
        alerts.append(_alert("stale_telemetry", "warning", "Telemetry stale", "Telemetry freshness has exceeded the safe threshold.", {"freshness_minutes": metrics.get("telemetry_freshness_minutes", 0)}))
    if runtime_metrics.get("stale_telemetry") or runtime_metrics.get("telemetry_state") == "stale":
        alerts.append(_alert("stale_telemetry_guard", "warning", "Stale telemetry preserved", "The last known safe telemetry snapshot is being served.", {"runtime_guard": runtime_metrics.get("runtime_guard", {}), "last_safe_snapshot_at": runtime_metrics.get("last_safe_snapshot_at")}))
    if metrics.get("parser_failure_rate", 0) > 0.25:
        alerts.append(_alert("high_parser_failure", "warning", "Parser failure rate high", "Parser failures exceed the advisory threshold.", {"parser_failure_rate": metrics.get("parser_failure_rate", 0)}))
    if metrics.get("auth_failures", 0):
        alerts.append(_alert("auth_anomaly", "warning", "Authentication failures", "Authentication failures have been recorded.", {"auth_failures": metrics.get("auth_failures", 0)}))
    if metrics.get("rate_limit_events", 0):
        alerts.append(_alert("rate_limit", "info", "Rate limiting active", "Rate limit events have been observed.", {"rate_limit_events": metrics.get("rate_limit_events", 0)}))
    if backup_status.get("backup_age_warning"):
        alerts.append(_alert("stale_backup", "warning", "Backup age warning", "The latest backup is older than the recommended threshold.", {"backup_status": backup_status}))
    if persistence_health.get("status") == "failing":
        alerts.append(_alert("persistence_failure", "critical", "Persistence degradation", "Persistence health has entered a failing state.", {"persistence": persistence_health}))
    if runtime.mode.value in {"production", "supervised_live"} and redis_config.backend == "local" and not redis_connection_ready():
        alerts.append(_alert("queue_backend", "warning", "Local queue backend", "Redis-ready queue backend is not configured.", {"queue_backend": redis_config.backend}))
    if not alerts:
        alerts.append(_alert("info", "info", "Operational alert baseline", "No active runtime alerts detected.", {}))
    from app.stabilization.telemetry_noise_reduction import reduce_telemetry_noise

    reduced = reduce_telemetry_noise(alerts=alerts, anomalies=[], limit=limit)
    retained_alerts = reduced.get("alerts", alerts)
    severities = sorted({alert["severity"] for alert in retained_alerts})
    return {
        "status": "ok" if alerts else "fallback",
        "generated_at": _now_iso(),
        "data_source": "runtime" if alerts else "fallback",
        "alerts": retained_alerts[: max(1, int(limit or 100))],
        "total": len(retained_alerts),
        "alert_severities": severities,
        "noise_reduction": reduced,
    }
