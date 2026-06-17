from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from .job_models import QueueJobStatus
from .queue_manager import get_jobs_by_status


def _queue_summary(limit: int = 50) -> Dict[str, Any]:
    jobs = get_jobs_by_status(limit=limit)
    return {
        "total_jobs": len(jobs),
        "blocked_jobs": len([job for job in jobs if job["status"] == QueueJobStatus.BLOCKED.value]),
    }


def get_queue_summary(limit: int = 50) -> Dict[str, Any]:
    summary = _queue_summary(limit=limit)
    summary["queue_health"] = get_queue_health(limit=limit)
    return summary


def find_stalled_jobs(limit: int = 50, stalled_after_minutes: int = 60) -> Dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=stalled_after_minutes)
    items = []
    for job in get_jobs_by_status(limit=limit):
        updated_at = str(job.get("updated_at") or "")
        if not updated_at:
            continue
        try:
            timestamp = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        except Exception:
            continue
        if timestamp < cutoff:
            items.append(job)
    return {"count": len(items), "items": items}


def get_queue_health(limit: int = 50) -> Dict[str, Any]:
    summary = _queue_summary(limit=limit)
    stalled = find_stalled_jobs(limit=limit, stalled_after_minutes=60)
    status = "degraded" if stalled["count"] or summary["blocked_jobs"] else "healthy"
    return {
        "status": status,
        "blocked_jobs": summary["blocked_jobs"],
        "stalled_jobs": stalled["count"],
        "summary": summary,
    }
