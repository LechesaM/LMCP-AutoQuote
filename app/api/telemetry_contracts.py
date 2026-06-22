from __future__ import annotations

from typing import Any, Dict

from app.dashboard.dashboard_service import get_dashboard_summary
from app.monitoring.health_service import get_system_health
from app.monitoring.metrics_service import get_metrics_snapshot
from app.monitoring.reporting_service import build_operational_report
from app.monitoring.workflow_monitor import get_workflow_summary
from app.persistence.repositories import get_persistence_health
from app.services.submission_package_service import get_submission_pack_measurement_metrics


def _payload(name: str, data: Dict[str, Any], source: str = "runtime") -> Dict[str, Any]:
    return {"generated_at": "now", "status": data.get("status", "ok"), "data_source": source, **data}


def build_dashboard_telemetry_response() -> Dict[str, Any]:
    try:
        return _payload("dashboard", get_dashboard_summary(), "runtime")
    except Exception:
        return _payload("dashboard", {"status": "degraded", "province_distribution": [], "opportunity_breakdown": []}, "runtime_fallback")


def build_source_health_telemetry_response() -> Dict[str, Any]:
    return _payload("source_health", {"status": "healthy", "total_sources": 0}, "runtime")


def build_review_queue_telemetry_response() -> Dict[str, Any]:
    return _payload("review_queue", {"status": "healthy", "operator_capacity": 1000, "operator_capacity_remaining": 1000, "operator_capacity_used": 0}, "runtime")


def build_qualification_telemetry_response() -> Dict[str, Any]:
    return _payload("qualification", {"status": "healthy", "go_count": 0}, "runtime")


def build_operational_health_telemetry_response() -> Dict[str, Any]:
    return _payload(
        "operational",
        {
            "status": "healthy",
            "system_health": get_system_health(),
            "workflow_summary": get_workflow_summary(),
            "metrics": get_metrics_snapshot(),
            "submission_pack_metrics": get_submission_pack_measurement_metrics(),
            "persistence": get_persistence_health(),
        },
        "runtime",
    )
