from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Dict, List

from app.operator_ops.operator_actions_service import get_operator_actions
from app.operator_ops.operator_activity_feed import get_operator_timeline
from app.productivity.review_queue_optimizer import build_review_queue_optimization_summary


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
    queue = build_review_queue_optimization_summary(limit=limit)

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
        "status": "ok" if reviewed else "fallback",
        "generated_at": _now_iso(),
        "data_source": "runtime" if reviewed else "fallback",
        "rfqs_reviewed_per_hour": throughput_per_hour,
        "review_completion_time_minutes": round(mean([float(item.get("queue_age_minutes", 0.0)) for item in queue.get("optimized_queue", [])]) if queue.get("optimized_queue") else 0.0, 2),
        "evidence_handling_time_minutes": round(mean([float(item.get("queue_age_minutes", 0.0)) for item in queue.get("optimized_queue", []) if item.get("stale_evidence")]) if [item for item in queue.get("optimized_queue", []) if item.get("stale_evidence")] else 0.0, 2),
        "escalation_frequency": len(escalations),
        "reassignment_frequency": len(reassignments),
        "queue_aging_trends": queue.get("summary", {}),
        "operator_throughput_trends": dict(by_operator),
        "timeline_gap_minutes": round(mean(timeline_gaps), 2) if timeline_gaps else 0.0,
        "throughput_bottlenecks": [item for item in queue.get("stale_rfqs", [])[:10]],
        "advisory_only": True,
    }
