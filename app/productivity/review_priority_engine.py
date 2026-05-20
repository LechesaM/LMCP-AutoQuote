from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from app.productivity.review_queue_optimizer import build_review_queue_optimization_summary


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_review_priority_summary(limit: int = 200) -> Dict[str, Any]:
    queue = build_review_queue_optimization_summary(limit=limit)
    items = list(queue.get("optimized_queue", []))
    priorities: Dict[str, List[Dict[str, Any]]] = {"urgent": [], "high": [], "medium": [], "low": []}
    for item in items:
        group = str(item.get("priority_group") or "low").lower()
        if group not in priorities:
            group = "low"
        priorities[group].append(item)
    escalation_recommendations = [
        {
            "tender_id": item.get("tender_id"),
            "title": item.get("title"),
            "recommendation": "escalate" if item.get("priority_group") in {"urgent", "high"} else "monitor",
            "reason": item.get("priority_reason", "queue pressure"),
        }
        for item in items[:15]
    ]
    return {
        "status": queue.get("status", "ok"),
        "generated_at": _now_iso(),
        "data_source": queue.get("data_source", "fallback"),
        "priority_score": round(sum(float(item.get("priority_score", 0.0)) for item in items[:50]) / max(1, min(50, len(items))), 2),
        "priority_groups": priorities,
        "escalation_recommendations": escalation_recommendations,
        "review_urgency": "high" if priorities["urgent"] or priorities["high"] else "normal",
        "overloaded_queue": bool(queue.get("overloaded_queue", False)),
    }

