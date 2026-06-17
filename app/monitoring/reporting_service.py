from __future__ import annotations

from typing import Any, Dict

from app.pilot import pilot_core
from .health_service import get_system_health
from .workflow_monitor import get_workflow_summary


def build_operational_report(limit: int = 50) -> Dict[str, Any]:
    readiness_report = pilot_core.build_pilot_readiness_report(limit=limit)
    return {
        "system_health": get_system_health(),
        "workflow_summary": get_workflow_summary(limit=limit),
        "pilot_mode": pilot_core.get_pilot_mode().value,
        "pilot_metrics": pilot_core.get_pilot_metrics(),
        "pilot_readiness_score": readiness_report.get("pilot_readiness_score", 0),
        "governance_compliance_score": readiness_report.get("governance_compliance_score", 0),
        "manual_governance_integrity_score": readiness_report.get("manual_governance_integrity_score", 0),
        "supervised_live_governance_summary": readiness_report.get("supervised_live_governance_summary", {}),
    }


def render_operational_report_text(report: Dict[str, Any]) -> str:
    return f"System status: {report.get('system_health', {}).get('status', 'unknown')}\nWorkflow summary: {report.get('workflow_summary', {}).get('total_workflows', 0)}"
