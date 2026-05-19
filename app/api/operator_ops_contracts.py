from __future__ import annotations

from typing import Any, Dict

from app.operator_ops import (
    acknowledge_alert,
    archive_rfq,
    assign_operator,
    get_operator_actions,
    get_operator_assignments,
    get_operator_capacity_snapshot,
    get_operator_notifications,
    get_operator_timeline,
    mark_evidence_incomplete,
    mark_reviewed,
    mark_supplier_quote_received,
    mark_waiting_pricing,
    reopen_review,
    request_clarification,
    escalate_review,
)
from app.operator_ops.operator_action_models import OperatorActionRequest


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _fallback_actions() -> dict:
    return {"status": "degraded", "generated_at": _now_iso(), "data_source": "fallback", "actions": [], "total": 0}


def _fallback_assignments() -> dict:
    return {
        "status": "degraded",
        "generated_at": _now_iso(),
        "data_source": "fallback",
        "assignments": [],
        "recommendations": [],
        "summary": {"totalAssignments": 0, "activeAssignments": 0, "operators": 10, "capacity": 1000},
        "capacity": {
            "status": "ok",
            "generated_at": _now_iso(),
            "data_source": "fallback",
            "teamSize": 10,
            "perOperatorDailyCapacity": 100,
            "totalDailyCapacity": 1000,
            "assignedToday": 0,
            "remainingCapacity": 1000,
            "overloaded": False,
            "recommendedLoad": 0,
        },
    }


def _fallback_timeline() -> dict:
    return {"status": "degraded", "generated_at": _now_iso(), "data_source": "fallback", "events": [], "total": 0}


def _fallback_notifications() -> dict:
    return {"status": "degraded", "generated_at": _now_iso(), "data_source": "fallback", "notifications": []}


def _fallback_capacity() -> dict:
    return {
        "status": "degraded",
        "generated_at": _now_iso(),
        "data_source": "fallback",
        "team_size": 10,
        "per_operator_daily_capacity": 100,
        "total_daily_capacity": 1000,
        "assigned_today": 0,
        "remaining_capacity": 1000,
        "overloaded": False,
        "recommended_load": 0,
    }


def _request(payload: Dict[str, Any]) -> OperatorActionRequest:
    return OperatorActionRequest.validate_payload(payload)


def build_operator_actions_response(limit: int = 100) -> Dict[str, Any]:
    try:
        return get_operator_actions(limit=limit)
    except Exception:
        return _fallback_actions()


def build_operator_assignments_response(limit: int = 100) -> Dict[str, Any]:
    try:
        return get_operator_assignments(limit=limit)
    except Exception:
        return _fallback_assignments()


def build_operator_timeline_response(limit: int = 100) -> Dict[str, Any]:
    try:
        return get_operator_timeline(limit=limit)
    except Exception:
        return _fallback_timeline()


def build_operator_notifications_response(limit: int = 100) -> Dict[str, Any]:
    try:
        return get_operator_notifications(limit=limit)
    except Exception:
        return _fallback_notifications()


def build_operator_capacity_response() -> Dict[str, Any]:
    try:
        return get_operator_capacity_snapshot()
    except Exception:
        return _fallback_capacity()
