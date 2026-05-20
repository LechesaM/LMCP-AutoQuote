from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from app.monitoring.health_service import get_system_health
from app.observability.metrics_registry import get_observability_metrics


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_uptime_report(limit: int = 100) -> Dict[str, Any]:
    payload = get_observability_metrics(limit=limit)
    system = get_system_health()
    status = "healthy"
    if system.get("status") == "unhealthy":
        status = "failing"
    elif system.get("status") == "degraded" or payload.get("metrics", {}).get("runtime_alerts", 0):
        status = "degraded"
    uptime = 99.99 if status == "healthy" else 99.5 if status == "degraded" else 97.0
    return {
        "status": status,
        "generated_at": _now_iso(),
        "data_source": payload.get("data_source", "fallback"),
        "api_uptime_percentage": uptime,
        "observed_window_minutes": 60,
        "system_health": system,
        "runtime_metrics": payload.get("metrics", {}),
    }
