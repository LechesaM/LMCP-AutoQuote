from __future__ import annotations

from typing import Any, Dict

from app.monitoring.workflow_monitor import get_workflow_summary
from app.orchestration.queue_monitor import get_queue_health, get_queue_summary
from app.operator_ops.operator_capacity_service import get_operator_capacity_snapshot


def build_review_queue_analytics(limit: int = 100) -> Dict[str, Any]:
    queue_summary = get_queue_summary(limit=limit)
    queue_health = get_queue_health(limit=limit)
    workflow_summary = get_workflow_summary(limit=limit)
    capacity = get_operator_capacity_snapshot()
    return {
        "status": "ok",
        "generated_at": queue_summary.get("checked_at"),
        "data_source": "runtime",
        "summary": {
            "pending_reviews": queue_health.get("summary", {}).get("queued_jobs", 0),
            "blocked_reviews": queue_health.get("summary", {}).get("blocked_jobs", 0),
            "queue_lag_minutes": queue_summary.get("queued_jobs", 0) * 5,
            "review_ready_pending": workflow_summary.get("review_ready_pending", 0),
            "proof_capture_pending": workflow_summary.get("proof_capture_pending", 0),
            "operator_capacity": capacity.get("total_daily_capacity", 1000),
            "operator_capacity_used": capacity.get("assigned_today", 0),
            "operator_capacity_remaining": capacity.get("remaining_capacity", 1000),
            "operator_utilization": round((capacity.get("assigned_today", 0) / max(1, capacity.get("total_daily_capacity", 1000))) * 100.0, 2),
        },
        "queue_health": queue_health,
        "workflow_summary": workflow_summary,
        "capacity": capacity,
    }

