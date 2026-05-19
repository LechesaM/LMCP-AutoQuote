from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from app.orchestration.queue_manager import get_jobs_by_status, get_queue_snapshot


def get_queue_summary(limit: int = 500) -> Dict[str, Any]:
    snapshot = get_queue_snapshot(limit=limit)
    by_status = snapshot.get("by_status", {})
    return {
        "status": "ok",
        "total_jobs": snapshot.get("total_jobs", 0),
        "queued_jobs": by_status.get("queued", 0),
        "running_jobs": by_status.get("running", 0),
        "completed_jobs": by_status.get("completed", 0),
        "failed_jobs": by_status.get("failed", 0),
        "retry_pending_jobs": by_status.get("retry_pending", 0),
        "blocked_jobs": by_status.get("blocked", 0),
        "archived_jobs": by_status.get("archived", 0),
        "snapshot": snapshot,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def get_queue_health(limit: int = 500, stalled_after_minutes: int = 240) -> Dict[str, Any]:
    stalled = find_stalled_jobs(limit=limit, stalled_after_minutes=stalled_after_minutes)
    summary = get_queue_summary(limit=limit)
    status = "healthy"
    if summary["failed_jobs"] or summary["blocked_jobs"] or stalled["count"]:
        status = "degraded"
    return {
        "status": status,
        "summary": summary,
        "stalled": stalled,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def find_stalled_jobs(limit: int = 500, stalled_after_minutes: int = 240) -> Dict[str, Any]:
    jobs = get_jobs_by_status(limit=limit)
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max(1, int(stalled_after_minutes)))
    stalled: List[Dict[str, Any]] = []
    for job in jobs:
        updated = str(job.get("updated_at") or job.get("created_at") or "")
        try:
            updated_at = datetime.fromisoformat(updated.replace("Z", "+00:00"))
        except Exception:
            continue
        if str(job.get("status") or "") in {"running", "retry_pending", "queued"} and updated_at < cutoff:
            stalled.append(
                {
                    "job_id": job.get("job_id", ""),
                    "tender_id": job.get("tender_id", ""),
                    "job_type": job.get("job_type", ""),
                    "status": job.get("status", ""),
                    "updated_at": updated,
                }
            )
    return {
        "status": "ok",
        "count": len(stalled),
        "items": stalled,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
