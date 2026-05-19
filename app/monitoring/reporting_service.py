from __future__ import annotations

from typing import Any, Dict, Optional

from app.monitoring.health_service import get_system_health
from app.monitoring.metrics_service import get_metrics_snapshot
from app.monitoring.runtime_diagnostics import get_runtime_diagnostics
from app.monitoring.workflow_monitor import find_invalid_workflows, find_stuck_workflows, get_workflow_summary
from app.pilot.pilot_readiness_report import build_pilot_readiness_report
from app.persistence.repositories import get_persistence_health


def build_operational_report(*, stuck_after_minutes: int = 240, limit: int = 500) -> Dict[str, Any]:
    metrics = get_metrics_snapshot()
    pilot = build_pilot_readiness_report(limit=limit)
    return {
        "system_health": get_system_health(),
        "workflow_summary": get_workflow_summary(limit=limit),
        "stuck_workflows": find_stuck_workflows(stuck_after_minutes=stuck_after_minutes, limit=limit),
        "invalid_workflows": find_invalid_workflows(limit=limit),
        "persistence": get_persistence_health(),
        "runtime_diagnostics": get_runtime_diagnostics(),
        "metrics": metrics,
        "pilot": pilot,
        "failure_summary": {
            "workflow_failures": metrics["metrics"].get("workflow_failures", 0),
            "persistence_failures": metrics["metrics"].get("persistence_failures", 0),
            "audit_failures": metrics["metrics"].get("audit_failures", 0),
            "pilot_failures": len(pilot.get("pilot_failures", [])),
            "pilot_recovery_events": pilot.get("pilot_metrics", {}).get("recovery_events", 0),
        },
    }


def render_operational_report_text(report: Optional[Dict[str, Any]] = None) -> str:
    report = report or build_operational_report()
    health = report.get("system_health", {})
    workflow = report.get("workflow_summary", {})
    metrics = report.get("metrics", {}).get("metrics", {})
    persistence = report.get("persistence", {})
    diagnostics = report.get("runtime_diagnostics", {})
    pilot = report.get("pilot", {})
    lines = [
        f"System status: {health.get('status', 'unknown')}",
        f"Environment: {health.get('environment', '')} / {health.get('production_mode', '')}",
        f"Workflow total: {workflow.get('total_workflows', 0)}",
        f"Refusals: {workflow.get('refusals', 0)}",
        f"Approvals pending: {workflow.get('approvals_pending', 0)}",
        f"Review ready pending: {workflow.get('review_ready_pending', 0)}",
        f"Proof capture pending: {workflow.get('proof_capture_pending', 0)}",
        f"DB available: {persistence.get('db_available', persistence.get('db_ready', False))}",
        f"Missing runtime directories: {len(diagnostics.get('missing_directories', []))}",
        f"Workflow failures: {metrics.get('workflow_failures', 0)}",
        f"Persistence failures: {metrics.get('persistence_failures', 0)}",
        f"Audit failures: {metrics.get('audit_failures', 0)}",
        f"Pilot mode: {pilot.get('pilot_mode', {}).get('pilot_mode', 'disabled')}",
        f"Pilot readiness score: {pilot.get('pilot_readiness_score', 0.0)}",
        f"Pilot failures: {len(pilot.get('pilot_failures', []))}",
    ]
    return "\n".join(lines)
