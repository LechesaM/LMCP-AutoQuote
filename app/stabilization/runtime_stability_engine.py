from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.observability.runtime_anomaly_detector import build_runtime_anomaly_report
from app.observability.sla_monitor import build_sla_monitoring_report
from app.operations.health_snapshots import get_health_snapshots
from app.operations.runtime_alerts import get_runtime_alerts
from app.operations.runtime_metrics import get_runtime_metrics
from app.core.runtime_config import get_runtime_config
from app.orchestration.worker_supervision import get_worker_supervision_report
from app.persistence.backup_scheduler import get_backup_status
from app.persistence.persistence_health import validate_persistence_health
from app.harvest.source_health import get_source_health_summary
from app.orchestration.queue_monitor import get_queue_summary

from ._shared import clamp, now_iso, safe_float, safe_int


def _snapshot_status(snapshot: Dict[str, Any]) -> str:
    payload = snapshot.get("payload") if isinstance(snapshot.get("payload"), dict) else snapshot
    health = payload.get("system_health") if isinstance(payload.get("system_health"), dict) else {}
    persistence = payload.get("persistence") if isinstance(payload.get("persistence"), dict) else {}
    queue = payload.get("queue_summary") if isinstance(payload.get("queue_summary"), dict) else {}
    statuses = {
        str(payload.get("status") or "").lower(),
        str(health.get("status") or "").lower(),
        str(persistence.get("status") or "").lower(),
        str(queue.get("status") or "").lower(),
    }
    statuses.discard("")
    if "unhealthy" in statuses or "failing" in statuses:
        return "failing"
    if "degraded" in statuses or "warning" in statuses:
        return "degraded"
    return "healthy"


def _count_degraded_snapshots(snapshots: List[Dict[str, Any]]) -> Dict[str, Any]:
    statuses = Counter(_snapshot_status(snapshot) for snapshot in snapshots)
    return {
        "healthy": statuses.get("healthy", 0),
        "degraded": statuses.get("degraded", 0),
        "failing": statuses.get("failing", 0),
        "window": len(snapshots),
    }


def build_runtime_stability_report(limit: int = 100) -> Dict[str, Any]:
    runtime = get_runtime_metrics(limit=limit)
    alerts = get_runtime_alerts(limit=limit)
    anomalies = build_runtime_anomaly_report(limit=limit)
    sla = build_sla_monitoring_report(limit=limit)
    snapshots = get_health_snapshots(limit=limit).get("snapshots", [])
    queue = get_queue_summary(limit=limit)
    sources = get_source_health_summary(limit=limit)
    workers = get_worker_supervision_report()
    backup = get_backup_status()
    persistence = validate_persistence_health()
    runtime_config = get_runtime_config()
    deployment = {
        "status": "healthy"
        if runtime_config.observability_enabled and not runtime_config.enable_legacy_routers
        else "degraded",
        "runtime_mode": runtime_config.mode.value,
        "observability_enabled": runtime_config.observability_enabled,
        "legacy_routers_enabled": runtime_config.enable_legacy_routers,
        "manual_production_enforced": runtime_config.manual_production_enforced,
    }

    queue_lag = safe_float(runtime.get("metrics", {}).get("queue_lag", 0.0))
    telemetry_freshness = safe_float(runtime.get("metrics", {}).get("telemetry_freshness_minutes", 0.0))
    worker_stale = safe_int(workers.get("stale_worker_count", 0))
    source_failures = safe_int(sources.get("failing_sources", 0))
    alert_total = safe_int(alerts.get("total", 0))
    anomaly_total = safe_int(anomalies.get("anomaly_count", 0))
    snapshot_breakdown = _count_degraded_snapshots(snapshots[-10:])

    score = 100.0
    score -= min(25.0, queue_lag)
    score -= min(15.0, telemetry_freshness)
    score -= min(15.0, source_failures * 3.0)
    score -= min(15.0, worker_stale * 5.0)
    score -= min(10.0, alert_total * 2.0)
    score -= min(10.0, anomaly_total * 2.0)
    if persistence.get("status") == "failing":
        score -= 20.0
    if deployment.get("status") != "healthy":
        score -= 15.0
    score = clamp(score, 0.0, 100.0)

    degradation_trends = [
        {"label": "recent_snapshots", "healthy": snapshot_breakdown["healthy"], "degraded": snapshot_breakdown["degraded"], "failing": snapshot_breakdown["failing"]},
        {"label": "queue_lag_minutes", "value": round(queue_lag, 2)},
        {"label": "telemetry_freshness_minutes", "value": round(telemetry_freshness, 2)},
        {"label": "worker_stale_count", "value": worker_stale},
        {"label": "source_failures", "value": source_failures},
        {"label": "alerts", "value": alert_total},
        {"label": "anomalies", "value": anomaly_total},
    ]
    operational_warnings: List[str] = []
    if queue_lag > 30:
        operational_warnings.append("Queue lag exceeds the stabilization threshold.")
    if telemetry_freshness > 15:
        operational_warnings.append("Telemetry freshness is stale.")
    if source_failures:
        operational_warnings.append("Source instability is present.")
    if worker_stale:
        operational_warnings.append("Worker heartbeat is stale.")
    if backup.get("backup_age_warning"):
        operational_warnings.append("Backup age warning is active.")
    if alerts.get("total", 0) > 0:
        operational_warnings.append("Runtime alerts are active.")
    if anomalies.get("anomaly_count", 0) > 0:
        operational_warnings.append("Runtime anomalies are present.")
    if deployment.get("status") != "healthy":
        operational_warnings.append("Deployment stability is unhealthy.")

    status = "healthy"
    if persistence.get("status") == "failing":
        status = "failing"
    elif operational_warnings or snapshot_breakdown["degraded"] or snapshot_breakdown["failing"]:
        status = "degraded"

    return {
        "status": status,
        "generated_at": now_iso(),
        "data_source": "runtime",
        "stability_score": round(score, 2),
        "degradation_trends": degradation_trends,
        "operational_warnings": operational_warnings,
        "signals": {
            "runtime": runtime,
            "alerts": alerts,
            "anomalies": anomalies,
            "sla": sla,
            "queue": queue,
            "sources": sources,
            "workers": workers,
            "backup": backup,
            "persistence": persistence,
            "deployment": deployment,
            "runtime_config": {
                "mode": runtime_config.mode.value,
                "observability_enabled": runtime_config.observability_enabled,
                "legacy_routers_enabled": runtime_config.enable_legacy_routers,
                "manual_production_enforced": runtime_config.manual_production_enforced,
            },
        },
        "snapshot_health": snapshot_breakdown,
        "queue_lag_minutes": round(queue_lag, 2),
        "telemetry_freshness_minutes": round(telemetry_freshness, 2),
        "worker_stale_count": worker_stale,
        "source_failure_count": source_failures,
        "alert_count": alert_total,
        "anomaly_count": anomaly_total,
        "window_size": len(snapshots),
    }
