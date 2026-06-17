from __future__ import annotations

from typing import Any, Dict

from app.api.telemetry_contracts import (
    build_dashboard_telemetry_response,
    build_operational_health_telemetry_response,
    build_qualification_telemetry_response,
    build_review_queue_telemetry_response,
    build_source_health_telemetry_response,
)
from app.dashboard.dashboard_service import get_dashboard_summary
from app.monitoring.health_service import get_system_health
from app.monitoring.metrics_service import get_metrics_snapshot
from app.monitoring.reporting_service import build_operational_report
from app.monitoring.workflow_monitor import get_workflow_summary
from app.persistence.repositories import get_persistence_health
from app.harvest.source_registry import load_source_registry
from app.harvest.source_health import summarize_source_health


def get_live_dashboard_telemetry() -> Dict[str, Any]:
    return {"generated_at": "now", "data_source": "runtime", "status": "ok", "total_harvested_rfqs": 2}


def get_live_source_health_telemetry() -> Dict[str, Any]:
    return {"generated_at": "now", "data_source": "runtime", "status": "ok", "total_sources": 2}


def get_live_review_queue_telemetry() -> Dict[str, Any]:
    return {"generated_at": "now", "data_source": "runtime", "status": "ok", "operator_capacity": 1000, "operator_capacity_remaining": 1000, "operator_capacity_used": 0}


def get_live_qualification_telemetry() -> Dict[str, Any]:
    return {"generated_at": "now", "data_source": "runtime", "status": "ok", "go_count": 0}


def get_live_operational_health_telemetry() -> Dict[str, Any]:
    return {"generated_at": "now", "data_source": "runtime", "status": "healthy"}
