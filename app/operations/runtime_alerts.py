from __future__ import annotations

from typing import Any, Dict, List

from .runtime_metrics import get_runtime_metrics


def _severity_for_issue(issue: Dict[str, Any]) -> str:
    status = str(issue.get("status") or "").lower()
    if status in {"failed", "failing", "error", "critical"}:
        return "critical"
    if status in {"degraded", "warning", "warn", "stale"}:
        return "warning"
    return "info"


def get_runtime_alerts(limit: int = 25) -> Dict[str, Any]:
    metrics = get_runtime_metrics(limit=limit)
    alert_rows: List[Dict[str, Any]] = []

    system_health = metrics.get("system_health") or {}
    persistence = metrics.get("persistence") or {}
    worker_supervision = metrics.get("worker_supervision") or {}

    if str(system_health.get("status") or "").lower() not in {"ok", "healthy"}:
        alert_rows.append({"category": "system", "status": system_health.get("status"), "message": "system health degraded"})
    if str(persistence.get("status") or "").lower() not in {"ok", "healthy"}:
        alert_rows.append({"category": "persistence", "status": persistence.get("status"), "message": "persistence health degraded"})
    if int(worker_supervision.get("stale_worker_count") or 0) > 0:
        alert_rows.append({"category": "workers", "status": "warning", "message": "stale workers detected"})
    if bool(metrics.get("stale_telemetry")):
        alert_rows.append({"category": "telemetry", "status": "warning", "message": "runtime telemetry is stale"})

    alert_severities = sorted({ _severity_for_issue(alert) for alert in alert_rows })
    return {
        "status": "ok" if not alert_rows else "fallback",
        "generated_at": metrics.get("generated_at"),
        "alerts": alert_rows,
        "alert_severities": alert_severities,
        "count": len(alert_rows),
    }
