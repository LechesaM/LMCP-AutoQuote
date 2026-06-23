from __future__ import annotations

from typing import Any, Dict, List

from .dead_letter_queue import list_dlq
from .durable_queue import get_queue_depth
from .worker_supervision import detect_stale_workers


def get_worker_supervision_report() -> Dict[str, Any]:
    stale = detect_stale_workers(stale_after_minutes=5)
    return {
        "status": "degraded" if stale else "healthy",
        "stale_worker_count": len(stale),
        "stale_workers": stale,
    }


def detect_queue_recovery_needs() -> Dict[str, Any]:
    depth = get_queue_depth()
    dlq = list_dlq()
    worker_report = get_worker_supervision_report()
    counts = dict(depth.get("counts") or {})
    blocked_operator_jobs = int(counts.get("running", 0)) + int(counts.get("retry_pending", 0)) + int(counts.get("failed", 0)) + int(dlq.get("count", 0)) + int(worker_report.get("stale_worker_count", 0))
    status = "degraded" if blocked_operator_jobs else "healthy"
    warnings: List[str] = []
    if counts.get("retry_pending", 0):
        warnings.append("retry pending jobs present")
    if dlq.get("count", 0):
        warnings.append("dead-letter queue has items")
    if worker_report.get("stale_worker_count", 0):
        warnings.append("stale workers detected")
    return {
        "status": status,
        "blocked_operator_jobs": blocked_operator_jobs,
        "queue_depth": depth,
        "dlq": dlq,
        "worker_supervision": worker_report,
        "warnings": warnings,
    }

