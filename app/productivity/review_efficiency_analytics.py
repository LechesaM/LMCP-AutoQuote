from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Dict, List

from app.operator_ops.operator_actions_service import get_operator_actions
from app.operator_ops.operator_activity_feed import get_operator_timeline


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def build_review_efficiency_analytics(limit: int = 200) -> Dict[str, Any]:
    actions = get_operator_actions(limit=limit).get("actions", [])
    timeline = get_operator_timeline(limit=limit).get("events", [])

    reviewed = [item for item in actions if str(item.get("action")) == "mark_reviewed"]
    evidence = [item for item in actions if str(item.get("action")) == "mark_evidence_incomplete"]
    escalations = [item for item in actions if str(item.get("action")) == "escalate_review"]
    reassignments = [item for item in actions if str(item.get("action")) == "assign_operator"]

    by_operator = Counter(str(item.get("operator_id") or "unassigned") for item in reviewed)
    timeline_gaps: List[float] = []
    timestamps = sorted([ts for ts in (_parse_iso(item.get("created_at")) for item in timeline) if ts])
    for left, right in zip(timestamps, timestamps[1:]):
        timeline_gaps.append((right - left).total_seconds() / 60.0)

    throughput_per_hour = 0.0
    if timestamps:
        duration = max(1.0, (timestamps[-1] - timestamps[0]).total_seconds() / 3600.0)
        throughput_per_hour = round(len(reviewed) / duration, 2)
    else:
        throughput_per_hour = float(len(reviewed))

    return {
        "status": "healthy" if reviewed else "fallback",
        "generated_at": _now_iso(),
        "data_source": "runtime" if reviewed else "fallback",
        "rfqs_reviewed_per_hour": throughput_per_hour,
        "review_completion_time_minutes": round(mean([float(item.get("queue_age_minutes", item.get("age_minutes", 0.0))) for item in reviewed]) if reviewed else 0.0, 2),
        "evidence_handling_time_minutes": round(mean([float(item.get("queue_age_minutes", item.get("age_minutes", 0.0))) for item in evidence]) if evidence else 0.0, 2),
        "escalation_frequency": len(escalations),
        "reassignment_frequency": len(reassignments),
        "queue_aging_trends": {
            "reviewed_count": len(reviewed),
            "evidence_count": len(evidence),
            "escalation_count": len(escalations),
            "reassignment_count": len(reassignments),
        },
        "operator_throughput_trends": dict(by_operator),
        "timeline_gap_minutes": round(mean(timeline_gaps), 2) if timeline_gaps else 0.0,
        "throughput_bottlenecks": [
            {
                "operator_id": str(item.get("operator_id") or "unassigned"),
                "action": str(item.get("action") or ""),
                "queue_age_minutes": float(item.get("queue_age_minutes", item.get("age_minutes", 0.0)) or 0.0),
            }
            for item in reviewed[:10]
        ],
        "advisory_only": True,
    }
