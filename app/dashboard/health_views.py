from __future__ import annotations

from typing import Any, Dict

from .dashboard_service import get_dashboard_summary


def get_dashboard_health() -> Dict[str, Any]:
    summary = get_dashboard_summary()
    return {
        "status": "healthy",
        "system_health": {"status": "healthy"},
        "summary": summary,
    }

