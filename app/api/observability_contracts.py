from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from app.observability.alert_router import build_alert_routing_summary
from app.observability.grafana_dashboards import build_grafana_dashboard_bundle
from app.observability.log_aggregation import build_log_aggregation_summary
from app.observability.prometheus_metrics import build_prometheus_metrics_export
from app.observability.runtime_anomaly_detector import build_runtime_anomaly_report
from app.observability.runtime_performance_monitor import build_runtime_performance_report
from app.observability.sentry_integration import build_sentry_status
from app.observability.sla_monitor import build_sla_monitoring_report
from app.observability.uptime_monitor import build_uptime_report


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_observability_prometheus_response(limit: int = 100) -> Dict[str, Any]:
    payload = build_prometheus_metrics_export(limit=limit)
    return {
        "status": payload.get("status", "degraded"),
        "generated_at": payload.get("generated_at", _now_iso()),
        "data_source": payload.get("data_source", "fallback"),
        "metrics_count": payload.get("metrics_count", 0),
        "metrics": payload.get("metrics", {}),
        "text": payload.get("text", ""),
    }


def build_observability_grafana_response(limit: int = 100) -> Dict[str, Any]:
    payload = build_grafana_dashboard_bundle(limit=limit)
    return {
        "status": payload.get("status", "ok"),
        "generated_at": payload.get("generated_at", _now_iso()),
        "data_source": payload.get("data_source", "runtime"),
        "dashboards": payload.get("dashboards", []),
        "count": payload.get("count", 0),
    }


def build_observability_sentry_response() -> Dict[str, Any]:
    payload = build_sentry_status()
    return {
        "status": payload.get("status", "fallback"),
        "generated_at": payload.get("generated_at", _now_iso()),
        "data_source": payload.get("data_source", "fallback"),
        "sentry": payload.get("sentry", {}),
    }


def build_observability_sla_response(limit: int = 100) -> Dict[str, Any]:
    payload = build_sla_monitoring_report(limit=limit)
    return {
        "status": payload.get("status", "degraded"),
        "generated_at": payload.get("generated_at", _now_iso()),
        "data_source": payload.get("data_source", "fallback"),
        "sla": payload,
    }


def build_observability_anomalies_response(limit: int = 100) -> Dict[str, Any]:
    payload = build_runtime_anomaly_report(limit=limit)
    return {
        "status": payload.get("status", "degraded"),
        "generated_at": payload.get("generated_at", _now_iso()),
        "data_source": payload.get("data_source", "fallback"),
        "anomalies": payload.get("anomalies", []),
        "anomaly_count": payload.get("anomaly_count", 0),
        "severity_counts": payload.get("severity_counts", {}),
    }


def build_observability_alerts_response(limit: int = 100) -> Dict[str, Any]:
    payload = build_alert_routing_summary(limit=limit)
    return {
        "status": payload.get("status", "fallback"),
        "generated_at": payload.get("generated_at", _now_iso()),
        "data_source": payload.get("data_source", "fallback"),
        "alerts": payload.get("routes", []),
        "route_count": payload.get("route_count", 0),
        "category_counts": payload.get("category_counts", {}),
        "target_counts": payload.get("target_counts", {}),
        "advisory_only": payload.get("advisory_only", True),
    }


def build_observability_logs_response(limit: int = 100) -> Dict[str, Any]:
    payload = build_log_aggregation_summary(limit=limit)
    return {
        "status": payload.get("status", "fallback"),
        "generated_at": payload.get("generated_at", _now_iso()),
        "data_source": payload.get("data_source", "fallback"),
        "logs": payload,
    }


def build_observability_uptime_response(limit: int = 100) -> Dict[str, Any]:
    payload = build_uptime_report(limit=limit)
    return {
        "status": payload.get("status", "degraded"),
        "generated_at": payload.get("generated_at", _now_iso()),
        "data_source": payload.get("data_source", "fallback"),
        "uptime": payload,
    }


def build_observability_performance_response(limit: int = 100) -> Dict[str, Any]:
    payload = build_runtime_performance_report(limit=limit)
    return {
        "status": payload.get("status", "degraded"),
        "generated_at": payload.get("generated_at", _now_iso()),
        "data_source": payload.get("data_source", "fallback"),
        "performance": payload,
    }
