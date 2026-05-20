from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.runtime_paths import get_runtime_paths
from app.orchestration.job_models import QueueJobStatus, QueueJobType
from app.orchestration.job_history import append_history_event
from app.orchestration.retry_policy import should_retry, calculate_retry_delay


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path() -> Path:
    return get_runtime_paths().manual_production_file("durable_queue.jsonl")


def _read() -> List[Dict[str, Any]]:
    path = _path()
    if not path.exists():
        return []
    items: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                items.append(payload)
    except Exception:
        return []
    return items


def _append(record: Dict[str, Any]) -> Dict[str, Any]:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return record


def _latest_jobs() -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for record in _read():
        job_id = str(record.get("job_id") or "")
        if job_id:
            latest[job_id] = record
    return latest


def enqueue_job(*, tender_id: str, job_type: QueueJobType | str, actor: str = "", operator: str = "", workflow_stage: str = "", payload: Optional[Dict[str, Any]] = None, max_attempts: int = 3) -> Dict[str, Any]:
    record = {
        "job_id": f"job-{uuid4().hex}",
        "tender_id": tender_id,
        "job_type": job_type.value if isinstance(job_type, QueueJobType) else str(job_type),
        "status": QueueJobStatus.QUEUED.value,
        "actor": actor,
        "operator": operator,
        "workflow_stage": workflow_stage,
        "attempt_count": 0,
        "max_attempts": int(max_attempts or 3),
        "payload": payload or {},
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    _append(record)
    append_history_event("enqueue", record)
    return record


def dequeue_job() -> Dict[str, Any]:
    latest = _latest_jobs()
    queued = [job for job in latest.values() if str(job.get("status") or "") == QueueJobStatus.QUEUED.value]
    if not queued:
        return {}
    job = sorted(queued, key=lambda item: str(item.get("created_at") or ""))[0]
    job["status"] = QueueJobStatus.RUNNING.value
    job["updated_at"] = _now_iso()
    _append(job)
    append_history_event("dequeue", job)
    return job


def acknowledge_job(job_id: str) -> Dict[str, Any]:
    latest = _latest_jobs().get(str(job_id))
    if not latest:
        raise ValueError(f"Unknown job: {job_id}")
    latest["status"] = QueueJobStatus.COMPLETED.value
    latest["updated_at"] = _now_iso()
    _append(latest)
    append_history_event("acknowledge", latest)
    return latest


def fail_job(job_id: str, reason: str = "") -> Dict[str, Any]:
    latest = _latest_jobs().get(str(job_id))
    if not latest:
        raise ValueError(f"Unknown job: {job_id}")
    latest["status"] = QueueJobStatus.FAILED.value
    latest["failure_reason"] = reason
    latest["updated_at"] = _now_iso()
    latest["attempt_count"] = int(latest.get("attempt_count", 0) or 0) + 1
    _append(latest)
    append_history_event("fail", latest)
    if should_retry(latest):
        retry_job(job_id, reason=reason)
    else:
        from app.orchestration.dead_letter_queue import move_to_dlq

        move_to_dlq(latest, reason=reason)
    return latest


def retry_job(job_id: str, reason: str = "") -> Dict[str, Any]:
    latest = _latest_jobs().get(str(job_id))
    if not latest:
        raise ValueError(f"Unknown job: {job_id}")
    if not should_retry(latest):
        raise ValueError(f"Job {job_id} is not eligible for retry")
    latest["status"] = QueueJobStatus.RETRY_PENDING.value
    latest["retry_delay_seconds"] = calculate_retry_delay(int(latest.get("attempt_count", 0) or 0))
    latest["updated_at"] = _now_iso()
    _append(latest)
    append_history_event("retry", latest)
    return latest


def get_queue_depth() -> Dict[str, Any]:
    latest = _latest_jobs().values()
    counts: Dict[str, int] = {}
    for job in latest:
        status = str(job.get("status") or "")
        counts[status] = counts.get(status, 0) + 1
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": "runtime" if counts else "fallback",
        "depth": counts.get(QueueJobStatus.QUEUED.value, 0),
        "counts": counts,
    }


def get_queue_health() -> Dict[str, Any]:
    depth = get_queue_depth()
    latest = _latest_jobs().values()
    blocked = len([job for job in latest if str(job.get("status") or "") == QueueJobStatus.BLOCKED.value])
    failed = len([job for job in latest if str(job.get("status") or "") == QueueJobStatus.FAILED.value])
    return {
        "status": "degraded" if blocked or failed else "healthy",
        "generated_at": _now_iso(),
        "data_source": depth.get("data_source", "fallback"),
        "depth": depth.get("depth", 0),
        "blocked": blocked,
        "failed": failed,
        "retry_pending": len([job for job in latest if str(job.get("status") or "") == QueueJobStatus.RETRY_PENDING.value]),
        "last_updated_at": max((str(job.get("updated_at") or "") for job in latest), default=""),
    }
