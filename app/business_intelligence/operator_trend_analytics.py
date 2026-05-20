from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from app.operator_ops.operator_actions_service import get_operator_actions
from app.operator_ops.operator_assignment_service import get_operator_assignments
from app.operator_ops.operator_activity_feed import get_operator_timeline
from ._shared import now_iso, parse_iso, safe_float


def build_operator_trend_analytics(limit: int = 100) -> Dict[str, Any]:
    actions = get_operator_actions(limit=limit).get("actions", [])
    assignments = get_operator_assignments(limit=limit).get("assignments", [])
    timeline = get_operator_timeline(limit=limit).get("events", [])
    throughput = Counter(str(item.get("operator_id") or "unassigned") for item in actions if str(item.get("action")) == "mark_reviewed")
    escalations = Counter(str(item.get("operator_id") or "unassigned") for item in actions if str(item.get("action")) == "escalate_review")
    queue_ownership = Counter(str(item.get("operator_id") or "unassigned") for item in assignments)
    reviews_per_hour = safe_float(len([item for item in actions if str(item.get("action")) == "mark_reviewed"]))
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "data_source": "runtime" if actions or assignments else "fallback",
        "summary": {
            "average_reviews_per_operator": round(sum(throughput.values()) / max(1, len(queue_ownership)), 2),
            "throughput_trend_count": len(throughput),
            "escalation_trend_count": len(escalations),
            "queue_ownership_trend_count": len(queue_ownership),
            "review_efficiency_trend": reviews_per_hour,
        },
        "throughput_trends": dict(throughput),
        "escalation_trends": dict(escalations),
        "queue_ownership_trends": dict(queue_ownership),
        "review_efficiency_trends": {
            "reviews_per_hour": reviews_per_hour,
            "timeline_events": len(timeline),
        },
    }

