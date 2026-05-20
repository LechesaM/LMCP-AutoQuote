from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from app.core.runtime_paths import get_runtime_paths
from app.observability.metrics_registry import get_observability_metrics
from app.persistence.persistence_health import validate_persistence_health
from app.productivity.review_efficiency_analytics import build_review_efficiency_analytics


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_frontend_build_freshness_minutes() -> float:
    root = get_runtime_paths().project_root
    dist_index = root / "frontend" / "command-centre" / "dist" / "index.html"
    if not dist_index.exists():
        return -1.0
    age_minutes = max(0.0, (datetime.now(timezone.utc).timestamp() - dist_index.stat().st_mtime) / 60.0)
    return round(age_minutes, 2)


def build_runtime_performance_report(limit: int = 100) -> Dict[str, Any]:
    payload = get_observability_metrics(limit=limit)
    metrics = payload.get("metrics", {})
    persistence = validate_persistence_health()
    api_latency_ms = float(metrics.get("api_latency_ms", 0.0))
    queue_response_time_ms = round(float(metrics.get("queue_lag_minutes", 0.0)) * 1000.0, 2)
    db_response_health = persistence.get("status", "degraded")
    frontend_build_freshness_minutes = _build_frontend_build_freshness_minutes()
    productivity = build_review_efficiency_analytics(limit=limit)
    deployment_health = "healthy"
    if db_response_health == "failing" or api_latency_ms > 1000.0:
        deployment_health = "failing"
    elif api_latency_ms > 300.0 or queue_response_time_ms > 30000.0 or frontend_build_freshness_minutes > 60.0:
        deployment_health = "degraded"
    return {
        "status": deployment_health,
        "generated_at": _now_iso(),
        "data_source": payload.get("data_source", "fallback"),
        "api_latency_ms": api_latency_ms,
        "queue_response_time_ms": queue_response_time_ms,
        "db_response_health": db_response_health,
        "frontend_build_freshness_minutes": frontend_build_freshness_minutes,
        "deployment_health": deployment_health,
        "telemetry_freshness_minutes": float(metrics.get("telemetry_freshness_minutes", 0.0)),
        "review_throughput_per_hour": float(productivity.get("rfqs_reviewed_per_hour", 0.0)),
        "review_efficiency_minutes": float(productivity.get("review_completion_time_minutes", 0.0)),
    }
