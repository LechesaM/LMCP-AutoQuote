from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean
from typing import Any, Dict

from app.core.runtime_config import get_runtime_config
from app.monitoring.metrics_service import get_metrics_snapshot
from app.monitoring.workflow_monitor import get_workflow_summary
from app.operations.incident_tracker import get_incident_summary
from app.operations.runtime_alerts import get_runtime_alerts
from app.operations.runtime_metrics import get_runtime_metrics
from app.orchestration.dead_letter_queue import list_dlq
from app.orchestration.redis_config import get_redis_config, redis_connection_ready
from app.orchestration.worker_supervision import get_worker_supervision_report
from app.persistence.backup_scheduler import get_backup_status
from app.persistence.persistence_health import validate_persistence_health


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return int(default)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _data_source(*sources: str) -> str:
    normalized = {str(source).strip().lower() for source in sources if str(source).strip()}
    normalized.discard("ok")
    if not normalized:
        return "fallback"
    if normalized == {"runtime"}:
        return "runtime"
    if normalized == {"persistence"}:
        return "persistence"
    if normalized == {"fallback"}:
        return "fallback"
    return "mixed"


def get_observability_metrics(limit: int = 100) -> Dict[str, Any]:
    runtime = get_runtime_metrics(limit=limit)
    metrics = get_metrics_snapshot().get("metrics", {})
    workflow = get_workflow_summary(limit=limit)
    alerts = get_runtime_alerts(limit=limit)
    incidents = get_incident_summary(limit=limit)
    backup = get_backup_status()
    persistence = validate_persistence_health()
    workers = get_worker_supervision_report()
    queue_backend = get_redis_config()
    dlq = list_dlq()
    system_runtime = get_runtime_config()

    observability_metrics = {
        "rfqs_harvested": _safe_float(runtime.get("metrics", {}).get("rfqs_harvested_per_hour", 0.0)),
        "rfqs_qualified": _safe_int(metrics.get("rfqs_evaluated", 0)),
        "review_throughput": _safe_int(metrics.get("reviews_recorded", 0)),
        "queue_lag_minutes": _safe_float(runtime.get("metrics", {}).get("queue_lag", 0)),
        "operator_utilization": _safe_float(runtime.get("metrics", {}).get("operator_utilization", 0.0)),
        "source_availability": _safe_float(runtime.get("metrics", {}).get("source_availability", 0.0)),
        "parser_failure_rate": _safe_float(runtime.get("metrics", {}).get("parser_failure_rate", 0.0)),
        "auth_failures": _safe_int(runtime.get("metrics", {}).get("auth_failures", 0)),
        "api_latency_ms": _safe_float(runtime.get("metrics", {}).get("api_latency_ms", 0.0)),
        "runtime_alerts": _safe_int(alerts.get("total", 0)),
        "dlq_count": _safe_int(dlq.get("count", 0)),
        "backup_age_days": _safe_float(backup.get("latest_backup_age_days", -1)),
        "worker_health": 1.0 if _safe_int(workers.get("stale_worker_count", 0)) == 0 else 0.0,
        "uptime_percent": 99.99 if system_runtime.mode.value != "production" or persistence.get("status") != "failing" else 99.0,
        "telemetry_freshness_minutes": _safe_float(runtime.get("metrics", {}).get("telemetry_freshness_minutes", 0.0)),
        "workflow_failures": _safe_int(metrics.get("workflow_failures", 0)),
        "persistence_failures": _safe_int(metrics.get("persistence_failures", 0)),
        "audit_failures": _safe_int(metrics.get("audit_failures", 0)),
        "queue_backend_ready": 1 if redis_connection_ready() else 0,
    }
    if workflow.get("total_workflows", 0):
        observability_metrics["rfqs_harvested"] = max(
            observability_metrics["rfqs_harvested"],
            _safe_float(workflow.get("total_workflows", 0)),
        )
    if incidents.get("total_incidents", 0):
        observability_metrics["runtime_alerts"] = max(observability_metrics["runtime_alerts"], _safe_int(incidents.get("total_incidents", 0)))

    status = "healthy"
    if persistence.get("status") == "failing" or observability_metrics["workflow_failures"] or observability_metrics["persistence_failures"] or observability_metrics["audit_failures"]:
        status = "failing"
    elif any(
        [
            observability_metrics["runtime_alerts"],
            observability_metrics["parser_failure_rate"] > 0.15,
            observability_metrics["queue_lag_minutes"] > 30,
            observability_metrics["telemetry_freshness_minutes"] > 15,
            backup.get("backup_age_warning"),
            workers.get("stale_worker_count", 0),
        ]
    ):
        status = "degraded"

    return {
        "status": status,
        "generated_at": _now_iso(),
        "data_source": _data_source(runtime.get("data_source"), alerts.get("data_source"), incidents.get("data_source"), persistence.get("data_source")),
        "metrics": observability_metrics,
        "runtime_metrics": runtime,
        "alerts": alerts,
        "incidents": incidents,
        "backup_status": backup,
        "persistence_health": persistence,
        "workers": workers,
        "queue_backend": {
            "backend": queue_backend.backend,
            "configured": queue_backend.configured,
            "ready": redis_connection_ready(),
            "host": queue_backend.host,
            "port": queue_backend.port,
            "database": queue_backend.db,
        },
    }


def get_observability_overview(limit: int = 100) -> Dict[str, Any]:
    payload = get_observability_metrics(limit=limit)
    metrics = payload.get("metrics", {})
    runtime = payload.get("runtime_metrics", {})
    alerts = payload.get("alerts", {})
    incidents = payload.get("incidents", {})
    backup = payload.get("backup_status", {})
    persistence = payload.get("persistence_health", {})
    workers = payload.get("workers", {})
    return {
        "status": payload.get("status", "degraded"),
        "generated_at": payload.get("generated_at", _now_iso()),
        "data_source": payload.get("data_source", "fallback"),
        "summary": {
            "queue_backend": payload.get("queue_backend", {}).get("backend", "local"),
            "queue_backend_ready": payload.get("queue_backend", {}).get("ready", False),
            "observability_enabled": get_runtime_config().observability_enabled,
            "rfqs_harvested": metrics.get("rfqs_harvested", 0.0),
            "rfqs_qualified": metrics.get("rfqs_qualified", 0),
            "review_throughput": metrics.get("review_throughput", 0),
            "runtime_alerts": metrics.get("runtime_alerts", 0),
            "incident_count": incidents.get("total_incidents", 0),
            "backup_age_days": backup.get("latest_backup_age_days", -1),
            "worker_stale_count": workers.get("stale_worker_count", 0),
            "telemetry_freshness_minutes": metrics.get("telemetry_freshness_minutes", 0.0),
            "queue_lag_minutes": metrics.get("queue_lag_minutes", 0.0),
            "source_availability": metrics.get("source_availability", 0.0),
            "parser_failure_rate": metrics.get("parser_failure_rate", 0.0),
            "persistence_status": persistence.get("status", "fallback"),
            "runtime_status": runtime.get("status", "ok"),
            "alert_status": alerts.get("status", "ok"),
        },
    }
