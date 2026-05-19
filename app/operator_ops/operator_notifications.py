from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from app.monitoring.workflow_monitor import get_workflow_summary
from app.orchestration.queue_monitor import get_queue_health
from app.harvest.source_health import get_source_health
from app.harvest.source_registry import load_source_registry
from app.operator_ops.operator_action_models import new_operator_id


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _notification(notification_type: str, severity: str, title: str, message: str, tender_id: str = "", operator_id: str = "", details: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return {
        "notification_id": new_operator_id(f"notif-{notification_type}"),
        "type": notification_type,
        "severity": severity,
        "title": title,
        "message": message,
        "tender_id": tender_id,
        "operator_id": operator_id,
        "acknowledged": False,
        "created_at": _now_iso(),
        "details": details or {},
    }


def get_operator_notifications(limit: int = 100) -> Dict[str, Any]:
    notifications: List[Dict[str, Any]] = []
    queue_health = get_queue_health(limit=limit)
    workflow_summary = get_workflow_summary(limit=limit)
    sources = load_source_registry().list_sources()[: max(1, int(limit or 100))]
    failing_sources = [source for source in sources if get_source_health(source.id).status in {"degraded", "failing", "disabled"}]

    if queue_health.get("stalled", {}).get("count", 0):
        notifications.append(_notification("stale_rfq", "warning", "Stale RFQs detected", "One or more RFQs have stalled in the queue.", details=queue_health.get("stalled", {})))
    if workflow_summary.get("pending_reviews", 0):
        notifications.append(_notification("overdue_review", "warning", "Pending reviews require attention", "Manual review items are awaiting operator attention.", details={"pending_reviews": workflow_summary.get("pending_reviews", 0)}))
    if queue_health.get("summary", {}).get("blocked_jobs", 0):
        notifications.append(_notification("queue_overload", "critical", "Queue overload detected", "Blocked jobs are present in the operational queue.", details=queue_health.get("summary", {})))
    if failing_sources:
        notifications.append(_notification("source_failure", "critical", "Source failures detected", f"{len(failing_sources)} sources are degraded or failing.", details={"sources": [source.id for source in failing_sources[:10]]}))
    if not notifications:
        notifications.append(_notification("info", "info", "No active notifications", "The operator workspace is currently stable.", details={}))
    return {"status": "ok", "generated_at": _now_iso(), "data_source": "runtime" if notifications else "fallback", "notifications": notifications[: max(1, int(limit or 100))]}
