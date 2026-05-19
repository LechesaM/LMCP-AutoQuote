from __future__ import annotations

from .health_service import ComponentHealth, SystemHealthSummary, get_component_health, get_system_health
from .metrics_service import increment_metric, get_metrics_snapshot, reset_test_metrics
from .runtime_diagnostics import RuntimeDiagnosticsReport, get_runtime_diagnostics
from .workflow_monitor import WorkflowMonitorSummary, find_invalid_workflows, find_stuck_workflows, get_workflow_summary


def build_operational_report(*args, **kwargs):
    from .reporting_service import build_operational_report as _build_operational_report

    return _build_operational_report(*args, **kwargs)


def render_operational_report_text(*args, **kwargs):
    from .reporting_service import render_operational_report_text as _render_operational_report_text

    return _render_operational_report_text(*args, **kwargs)

__all__ = [
    "ComponentHealth",
    "SystemHealthSummary",
    "RuntimeDiagnosticsReport",
    "WorkflowMonitorSummary",
    "build_operational_report",
    "find_invalid_workflows",
    "find_stuck_workflows",
    "get_component_health",
    "get_metrics_snapshot",
    "get_runtime_diagnostics",
    "get_system_health",
    "get_workflow_summary",
    "increment_metric",
    "render_operational_report_text",
    "reset_test_metrics",
]
