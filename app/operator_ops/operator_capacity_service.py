from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

TEAM_SIZE = 10
PER_OPERATOR_DAILY_CAPACITY = 100
TOTAL_DAILY_CAPACITY = 1000


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_operator_capacity_snapshot() -> Dict[str, Any]:
    from app.operator_ops.operator_assignment_service import get_operator_assignments, recommend_operator_assignments

    assignments = get_operator_assignments(limit=1000).get("assignments", [])
    recommended = recommend_operator_assignments(limit=25).get("recommended", [])
    assigned_today = len(assignments)
    recommended_load = len(recommended)
    remaining = max(0, TOTAL_DAILY_CAPACITY - assigned_today)
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": "runtime" if assignments else "fallback",
        "team_size": TEAM_SIZE,
        "per_operator_daily_capacity": PER_OPERATOR_DAILY_CAPACITY,
        "total_daily_capacity": TOTAL_DAILY_CAPACITY,
        "assigned_today": assigned_today,
        "remaining_capacity": remaining,
        "overloaded": assigned_today >= TOTAL_DAILY_CAPACITY,
        "recommended_load": recommended_load,
    }


def capacity_status() -> Dict[str, Any]:
    return get_operator_capacity_snapshot()
