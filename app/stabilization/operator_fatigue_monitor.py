from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any, Dict, List

from app.operator_ops.operator_activity_feed import get_operator_timeline
from app.operator_ops.operator_assignment_service import get_operator_assignments
from app.operator_ops.operator_capacity_service import get_operator_capacity_snapshot
from app.productivity.operator_focus_sessions import build_focus_session_summary
from app.productivity.review_efficiency_analytics import build_review_efficiency_analytics
from app.orchestration.queue_monitor import get_queue_summary

from ._shared import now_iso, safe_float, safe_int, safe_str


def build_operator_fatigue_report(limit: int = 200) -> Dict[str, Any]:
    assignments = get_operator_assignments(limit=limit).get("assignments", [])
    capacity = get_operator_capacity_snapshot()
    timeline = get_operator_timeline(limit=limit).get("events", [])
    focus = build_focus_session_summary(limit=limit)
    efficiency = build_review_efficiency_analytics(limit=limit)
    queue = get_queue_summary(limit=limit)

    per_operator: Dict[str, Dict[str, Any]] = {}
    for row in assignments:
        operator_id = safe_str(row.get("operator_id") or row.get("operatorId") or "unassigned", "unassigned")
        bucket = per_operator.setdefault(operator_id, {"assigned": 0, "overdue": 0, "priorities": [], "queue_age": []})
        bucket["assigned"] += 1
        bucket["priorities"].append(safe_float(row.get("priority") or 0))
        if str(row.get("status") or "").lower() not in {"completed", "reviewed", "archived"} and row.get("due_at"):
            bucket["overdue"] += 1
        bucket["queue_age"].append(safe_float(row.get("queue_age_minutes") or row.get("age_minutes") or 0.0))

    fatigue_rows: List[Dict[str, Any]] = []
    warnings: List[str] = []
    for operator_id, bucket in sorted(per_operator.items(), key=lambda item: (-item[1]["assigned"], item[0])):
        overload = safe_int(bucket["assigned"]) / max(1, safe_int(capacity.get("per_operator_daily_capacity", 100), 100))
        fatigue_score = round(min(100.0, overload * 100.0 + bucket["overdue"] * 12.0 + (mean(bucket["queue_age"]) if bucket["queue_age"] else 0.0) / 4.0), 2)
        if fatigue_score >= 80:
            warnings.append(f"{operator_id} appears heavily fatigued.")
        elif fatigue_score >= 55:
            warnings.append(f"{operator_id} is showing sustained workload pressure.")
        fatigue_rows.append(
            {
                "operator_id": operator_id,
                "assigned": bucket["assigned"],
                "overdue": bucket["overdue"],
                "average_priority": round(mean(bucket["priorities"]), 2) if bucket["priorities"] else 0.0,
                "average_queue_age_minutes": round(mean(bucket["queue_age"]), 2) if bucket["queue_age"] else 0.0,
                "fatigue_score": fatigue_score,
            }
        )

    if not fatigue_rows:
        for index in range(safe_int(capacity.get("team_size", 10), 10)):
            fatigue_rows.append(
                {
                    "operator_id": f"operator-{index + 1}",
                    "assigned": 0,
                    "overdue": 0,
                    "average_priority": 0.0,
                    "average_queue_age_minutes": 0.0,
                    "fatigue_score": 0.0,
                }
            )

    sustained_overload = len([row for row in fatigue_rows if row["fatigue_score"] >= 80])
    status = "healthy"
    if sustained_overload:
        status = "degraded"
    if sustained_overload >= 3 or safe_int(capacity.get("remaining_capacity", 1000), 1000) <= 0:
        status = "failing"

    return {
        "status": status,
        "generated_at": now_iso(),
        "data_source": "runtime" if assignments else "fallback",
        "fatigue_score": round(mean([row["fatigue_score"] for row in fatigue_rows]) if fatigue_rows else 0.0, 2),
        "warnings": warnings,
        "fatigue_rows": fatigue_rows,
        "workload_rebalance_recommendations": [
            {
                "operator_id": row["operator_id"],
                "recommendation": "rebalance" if row["fatigue_score"] >= 55 else "monitor",
                "reason": "sustained queue pressure" if row["fatigue_score"] >= 55 else "within acceptable bounds",
            }
            for row in fatigue_rows[:10]
        ],
        "signals": {
            "timeline_events": len(timeline),
            "focus_sessions": focus.get("summary", {}),
            "review_efficiency": {
                "rfqs_reviewed_per_hour": efficiency.get("rfqs_reviewed_per_hour", 0.0),
                "escalation_frequency": efficiency.get("escalation_frequency", 0),
                "reassignment_frequency": efficiency.get("reassignment_frequency", 0),
            },
            "queue_pressure": queue.get("summary", {}),
            "capacity": capacity,
        },
    }
