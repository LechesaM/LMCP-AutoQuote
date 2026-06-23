from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from ._durable_queue_store import (
    find_job,
    load_queue_state,
    next_job_id,
    normalize_job_type,
    queue_counts,
    queue_depth,
    save_queue_state,
    select_queued_job,
    update_job,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def enqueue_job(
    *,
    tender_id: str,
    job_type: Any,
    actor: str,
    operator: str,
    workflow_stage: str,
    payload: Dict[str, Any] | None = None,
    max_attempts: int = 3,
    idempotency_key: str | None = None,
) -> Dict[str, Any]:
    state = load_queue_state()
    normalized_key = str(idempotency_key or "").strip()
    if normalized_key:
        existing_job_id = state.get("idempotency_index", {}).get(normalized_key)
        if existing_job_id:
            existing = find_job(state, existing_job_id)
            if existing is not None:
                replay = dict(existing)
                replay["idempotent_replay"] = True
                return replay
    job = {
        "job_id": next_job_id(),
        "tender_id": str(tender_id),
        "job_type": normalize_job_type(job_type),
        "actor": str(actor),
        "operator": str(operator),
        "workflow_stage": str(workflow_stage),
        "payload": dict(payload or {}),
        "status": "pending",
        "attempts": 0,
        "max_attempts": int(max_attempts or 1),
        "created_at": _utc_now_iso(),
        "updated_at": _utc_now_iso(),
        "idempotency_key": normalized_key,
        "idempotent_replay": False,
    }
    state.setdefault("jobs", []).append(job)
    if normalized_key:
        state.setdefault("idempotency_index", {})[normalized_key] = job["job_id"]
    save_queue_state(state)
    return dict(job)


def dequeue_job() -> Dict[str, Any]:
    state = load_queue_state()
    job = select_queued_job(state)
    if job is None:
        return {}
    job["status"] = "running"
    job["started_at"] = _utc_now_iso()
    job["updated_at"] = _utc_now_iso()
    update_job(state, job)
    save_queue_state(state)
    return dict(job)


def acknowledge_job(job_id: str) -> Dict[str, Any]:
    state = load_queue_state()
    job = find_job(state, job_id)
    if job is None:
        return {"job_id": job_id, "status": "completed"}
    job["status"] = "completed"
    job["completed_at"] = _utc_now_iso()
    job["updated_at"] = _utc_now_iso()
    update_job(state, job)
    save_queue_state(state)
    return dict(job)


def fail_job(job_id: str, reason: str, actor: str | None = None, operator: str | None = None) -> Dict[str, Any]:
    state = load_queue_state()
    job = find_job(state, job_id)
    if job is None:
        return {"job_id": job_id, "status": "failed", "reason": reason}
    job["status"] = "failed"
    job["reason"] = str(reason)
    job["failed_at"] = _utc_now_iso()
    job["updated_at"] = _utc_now_iso()
    job["attempts"] = int(job.get("attempts", 0)) + 1
    update_job(state, job)
    save_queue_state(state)
    if int(job.get("attempts", 0)) >= int(job.get("max_attempts", 1)):
        from .dead_letter_queue import move_to_dlq

        move_to_dlq(job, reason=reason)
    return dict(job)


def get_queue_depth() -> Dict[str, Any]:
    state = load_queue_state()
    counts = queue_counts(state)
    return {"depth": queue_depth(state), "counts": counts, "updated_at": state.get("updated_at")}


def get_queue_health() -> Dict[str, Any]:
    depth = get_queue_depth()
    counts = dict(depth.get("counts") or {})
    from .dead_letter_queue import list_dlq

    dlq_count = len(list_dlq().get("items", []))
    status = "degraded" if counts.get("failed", 0) or counts.get("retry_pending", 0) or counts.get("blocked", 0) or dlq_count else "healthy"
    return {
        "status": status,
        "depth": depth.get("depth", 0),
        "counts": counts,
        "dlq_count": dlq_count,
    }
