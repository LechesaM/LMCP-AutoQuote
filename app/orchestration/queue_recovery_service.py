from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from app.orchestration.durable_queue import get_queue_depth, get_queue_health
from app.orchestration.dead_letter_queue import list_dlq
from app.orchestration.worker_supervision import get_worker_supervision_report


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def detect_queue_recovery_needs(stalled_after_minutes: int = 240) -> Dict[str, Any]:
    depth = get_queue_depth()
    health = get_queue_health()
    dlq = list_dlq()
    workers = get_worker_supervision_report()
    blockers: List[str] = []
    if depth.get("depth", 0) > 0 and workers.get("stale_worker_count", 0) > 0:
        blockers.append("stale worker and queued jobs detected")
    if dlq.get("count", 0) > 0:
        blockers.append("dead-letter queue contains items")
    if health.get("blocked", 0) > 0:
        blockers.append("blocked jobs detected")
    return {
        "status": "ok" if not blockers else "degraded",
        "generated_at": _now_iso(),
        "data_source": "runtime",
        "stalled_after_minutes": stalled_after_minutes,
        "stuck_jobs": depth.get("counts", {}).get("running", 0) + depth.get("counts", {}).get("retry_pending", 0),
        "failed_retries": depth.get("counts", {}).get("failed", 0),
        "stale_queued_jobs": depth.get("counts", {}).get("queued", 0),
        "orphaned_workflow_jobs": 0,
        "blocked_operator_jobs": health.get("blocked", 0),
        "recommendations": blockers,
        "worker_health": workers,
        "dlq": dlq,
    }


def recommend_queue_recovery() -> Dict[str, Any]:
    return detect_queue_recovery_needs()
