from __future__ import annotations

from typing import Any, Dict

from .dashboard_service import get_dashboard_summary, get_operational_summary


def get_operational_report_view() -> Dict[str, Any]:
    return {
        "dashboard_summary": get_dashboard_summary(),
        "operational_summary": get_operational_summary(),
    }

