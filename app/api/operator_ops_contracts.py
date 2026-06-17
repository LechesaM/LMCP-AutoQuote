from __future__ import annotations

from typing import Any, Dict

from app.operator_ops.operator_activity_feed import get_operator_timeline
from app.operator_ops.operator_assignment_service import get_operator_assignments
from app.operator_ops.operator_capacity_service import get_operator_capacity_snapshot
from app.operator_ops.operator_notifications import get_operator_notifications


def _payload(data: Dict[str, Any]) -> Dict[str, Any]:
    return {"generated_at": "now", "status": data.get("status", "ok"), "data_source": "runtime", **data}


def get_operator_actions() -> Dict[str, Any]:
    return {"items": []}


def build_operator_actions_response() -> Dict[str, Any]:
    try:
        return _payload(get_operator_actions())
    except Exception:
        return {"generated_at": "now", "status": "degraded", "data_source": "fallback"}


def build_operator_assignments_response() -> Dict[str, Any]:
    try:
        return _payload(get_operator_assignments())
    except Exception:
        return {"generated_at": "now", "status": "degraded", "data_source": "fallback"}


def build_operator_timeline_response() -> Dict[str, Any]:
    try:
        return _payload(get_operator_timeline())
    except Exception:
        return {"generated_at": "now", "status": "degraded", "data_source": "fallback"}


def build_operator_notifications_response() -> Dict[str, Any]:
    try:
        return _payload(get_operator_notifications())
    except Exception:
        return {"generated_at": "now", "status": "degraded", "data_source": "fallback"}


def build_operator_capacity_response() -> Dict[str, Any]:
    try:
        return _payload(get_operator_capacity_snapshot())
    except Exception:
        return {"generated_at": "now", "status": "degraded", "data_source": "fallback"}
