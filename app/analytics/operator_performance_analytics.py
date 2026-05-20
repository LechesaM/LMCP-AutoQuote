from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.operator_ops.operator_actions_service import get_operator_actions
from app.operator_ops.operator_assignment_service import get_operator_assignments
from app.operator_ops.operator_activity_feed import get_operator_timeline


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: Any):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def build_operator_performance_analytics(limit: int = 100) -> Dict[str, Any]:
    actions = get_operator_actions(limit=limit).get("actions", [])
    assignments = get_operator_assignments(limit=limit).get("assignments", [])
    timeline = get_operator_timeline(limit=limit).get("events", [])
    reviewed = [action for action in actions if str(action.get("action") or "") == "mark_reviewed"]
    escalations = [action for action in actions if str(action.get("action") or "") == "escalate_review"]
    acknowledgements = [action for action in actions if str(action.get("action") or "") == "acknowledge_alert"]
    assignment_by_tender = {str(item.get("tender_id") or ""): item for item in assignments}
    review_times: List[float] = []
    for action in reviewed:
        tender_id = str(action.get("tender_id") or "")
        assignment = assignment_by_tender.get(tender_id)
        if not assignment:
            continue
        assigned_at = _parse_iso(assignment.get("assigned_at"))
        reviewed_at = _parse_iso(action.get("created_at"))
        if assigned_at and reviewed_at and reviewed_at >= assigned_at:
            review_times.append((reviewed_at - assigned_at).total_seconds() / 60.0)
    operator_counts = Counter(str(item.get("operator_id") or "unassigned") for item in assignments)
    daily_reviews = Counter(str(action.get("operator_id") or "unassigned") for action in reviewed)
    overdue_reviews = sum(1 for item in assignments if _parse_iso(item.get("due_at")) and _parse_iso(item.get("due_at")) < datetime.now(timezone.utc))
    summary = {
        "reviewed_per_operator_day": dict(daily_reviews),
        "average_review_time_minutes": round(sum(review_times) / len(review_times), 2) if review_times else 0.0,
        "escalation_frequency": len(escalations),
        "overdue_review_frequency": overdue_reviews,
        "queue_ownership_distribution": dict(operator_counts),
        "alert_acknowledgement_frequency": len(acknowledgements),
        "review_completion_rate": round(len(reviewed) / max(1, len(assignments)), 4),
        "operators_seen": len(operator_counts),
        "assignment_count": len(assignments),
        "review_count": len(reviewed),
        "timeline_event_count": len(timeline),
    }
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": "runtime" if actions or assignments else "fallback",
        "summary": summary,
        "actions": actions[-max(1, int(limit or 100)) :],
        "assignments": assignments[-max(1, int(limit or 100)) :],
        "timeline": timeline[-max(1, int(limit or 100)) :],
    }
