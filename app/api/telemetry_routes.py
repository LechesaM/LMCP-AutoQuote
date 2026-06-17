from __future__ import annotations

from .telemetry_contracts import (
    build_dashboard_telemetry_response,
    build_operational_health_telemetry_response,
    build_qualification_telemetry_response,
    build_review_queue_telemetry_response,
    build_source_health_telemetry_response,
)
from app.services.quote_review_service import _run_with_timeout as _quote_review_run_with_timeout


def run_with_timeout(callback, timeout_seconds: int, timeout_label: str, fallback=None):
    try:
        return _quote_review_run_with_timeout(callback, timeout_seconds, timeout_label)
    except Exception:
        if fallback is not None:
            return fallback()
        return {"status": "timeout", "data_source": "timeout"}


def _dashboard_timeout_fallback():
    return {"generated_at": "now", "status": "degraded", "data_source": "runtime_fallback", "province_distribution": [], "opportunity_breakdown": []}


def _source_health_timeout_fallback():
    return {"generated_at": "now", "status": "degraded", "data_source": "runtime_fallback", "total_sources": 0}


def _review_queue_timeout_fallback():
    return {"generated_at": "now", "status": "degraded", "data_source": "runtime_fallback", "operator_capacity": 0, "operator_capacity_remaining": 0, "operator_capacity_used": 0}


def _qualification_timeout_fallback():
    return {"generated_at": "now", "status": "degraded", "data_source": "runtime_fallback", "go_count": 0}


def _operational_health_timeout_fallback():
    return {"generated_at": "now", "status": "degraded", "data_source": "runtime_fallback", "system_health": {}, "workflow_summary": {}, "metrics": {}, "persistence": {}}


def get_dashboard_telemetry():
    return run_with_timeout(build_dashboard_telemetry_response, 5, "dashboard", fallback=_dashboard_timeout_fallback)


def get_source_health_telemetry():
    return run_with_timeout(build_source_health_telemetry_response, 5, "source_health", fallback=_source_health_timeout_fallback)


def get_review_queue_telemetry():
    return run_with_timeout(build_review_queue_telemetry_response, 5, "review_queue", fallback=_review_queue_timeout_fallback)


def get_qualification_telemetry():
    return run_with_timeout(build_qualification_telemetry_response, 5, "qualification", fallback=_qualification_timeout_fallback)


def get_operational_health_telemetry():
    return run_with_timeout(build_operational_health_telemetry_response, 5, "operational_health", fallback=_operational_health_timeout_fallback)
