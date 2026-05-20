from __future__ import annotations

from typing import Any, Dict

from app.analytics.operator_performance_analytics import build_operator_performance_analytics
from app.analytics.review_queue_analytics import build_review_queue_analytics
from app.analytics.source_reliability_analytics import build_source_reliability_analytics
from app.operations.backup_validation import get_backup_validation_summary
from app.operations.incident_tracker import get_incident_summary
from app.operations.runtime_alerts import get_runtime_alerts
from app.operations.runtime_metrics import get_runtime_metrics


def build_runtime_metrics_response(limit: int = 100) -> Dict[str, Any]:
    payload = get_runtime_metrics(limit=limit)
    metrics = payload.get("metrics", {})
    return {
        "status": payload.get("status", "ok"),
        "generated_at": payload.get("generated_at"),
        "data_source": payload.get("data_source", "runtime"),
        "rfqs_harvested_per_hour": metrics.get("rfqs_harvested_per_hour", 0.0),
        "review_throughput": metrics.get("review_throughput", 0),
        "queue_lag": metrics.get("queue_lag", 0),
        "operator_utilization": metrics.get("operator_utilization", 0.0),
        "parser_failure_rate": metrics.get("parser_failure_rate", 0.0),
        "source_availability": metrics.get("source_availability", 0.0),
        "telemetry_freshness_minutes": metrics.get("telemetry_freshness_minutes", 0),
        "stale_telemetry": payload.get("stale_telemetry", False),
        "degraded_state": payload.get("degraded_state", False),
        "telemetry_state": payload.get("telemetry_state", "fresh"),
        "last_safe_snapshot_at": payload.get("last_safe_snapshot_at"),
        "last_safe_snapshot": payload.get("last_safe_snapshot", {}),
        "workflow_failures": metrics.get("workflow_failures", 0),
        "persistence_failures": metrics.get("persistence_failures", 0),
        "auth_failures": metrics.get("auth_failures", 0),
        "rate_limit_events": metrics.get("rate_limit_events", 0),
        "api_latency_ms": metrics.get("api_latency_ms", 0),
        "runtime_guard": payload.get("runtime_guard", {}),
        "system_health": payload.get("system_health", {}),
        "operator_capacity": payload.get("operator_capacity", {}),
        "queue_summary": payload.get("queue_summary", {}),
        "source_summary": payload.get("source_summary", {}),
        "persistence": payload.get("persistence", {}),
    }


def build_operator_analytics_response(limit: int = 100) -> Dict[str, Any]:
    payload = build_operator_performance_analytics(limit=limit)
    return {
        "status": payload.get("status", "ok"),
        "generated_at": payload.get("generated_at"),
        "data_source": payload.get("data_source", "runtime"),
        "summary": payload.get("summary", {}),
        "actions": payload.get("actions", []),
        "assignments": payload.get("assignments", []),
        "timeline": payload.get("timeline", []),
    }


def build_source_reliability_response(limit: int = 100) -> Dict[str, Any]:
    payload = build_source_reliability_analytics(limit=limit)
    return {
        "status": payload.get("status", "ok"),
        "generated_at": payload.get("generated_at"),
        "data_source": payload.get("data_source", "runtime"),
        "summary": payload.get("summary", {}),
        "top_failing_sources": payload.get("top_failing_sources", []),
        "top_reliable_sources": payload.get("top_reliable_sources", []),
        "source_status_counts": payload.get("source_status_counts", {}),
        "source_health": payload.get("source_health", {}),
    }


def build_incidents_response(limit: int = 100) -> Dict[str, Any]:
    payload = get_incident_summary(limit=limit)
    return {
        "status": payload.get("status", "ok"),
        "generated_at": payload.get("generated_at"),
        "data_source": payload.get("data_source", "runtime"),
        "total_incidents": payload.get("total_incidents", 0),
        "severity_counts": payload.get("severity_counts", {}),
        "status_counts": payload.get("status_counts", {}),
        "active_critical_incidents": payload.get("active_critical_incidents", 0),
        "incidents": payload.get("incidents", []),
    }


def build_runtime_alerts_response(limit: int = 100) -> Dict[str, Any]:
    payload = get_runtime_alerts(limit=limit)
    return {
        "status": payload.get("status", "ok"),
        "generated_at": payload.get("generated_at"),
        "data_source": payload.get("data_source", "runtime"),
        "alerts": payload.get("alerts", []),
        "total": payload.get("total", 0),
        "alert_severities": payload.get("alert_severities", []),
    }


def build_backup_validation_response() -> Dict[str, Any]:
    payload = get_backup_validation_summary()
    return {
        "status": payload.get("status", "ok"),
        "generated_at": payload.get("generated_at"),
        "data_source": payload.get("data_source", "runtime"),
        "backup_count": payload.get("backup_count", 0),
        "backup_dir": payload.get("backup_dir", ""),
        "latest_backup": payload.get("latest_backup", ""),
        "latest_backup_verified": payload.get("latest_backup_verified", False),
        "latest_backup_age_days": payload.get("latest_backup_age_days", 0),
        "audit_persistence_ok": payload.get("audit_persistence_ok", False),
        "restore_simulation": payload.get("restore_simulation", {}),
    }
