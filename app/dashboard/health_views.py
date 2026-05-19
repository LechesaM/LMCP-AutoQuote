from __future__ import annotations

from typing import Any, Dict

from app.monitoring.health_service import get_system_health
from app.monitoring.reporting_service import build_operational_report
from app.persistence.repositories import get_persistence_health


def get_health_summary() -> Dict[str, Any]:
    report = build_operational_report()
    return {
        "runtime_health": report.get("system_health", {}),
        "db_health": report.get("persistence", {}),
        "persistence_health": get_persistence_health(),
        "audit_health": report.get("system_health", {}).get("components", []),
        "workflow_health": report.get("workflow_summary", {}),
        "monitoring_health": report.get("runtime_diagnostics", {}),
    }


def get_dashboard_health() -> Dict[str, Any]:
    health = get_system_health()
    summary = get_health_summary()
    return {
        "status": health.get("status", "unknown"),
        "system_health": health,
        "summary": summary,
    }
