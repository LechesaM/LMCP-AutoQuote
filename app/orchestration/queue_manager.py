from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.runtime_paths import get_runtime_paths
from app.orchestration.job_history import append_failure_history, append_history_event, append_retry_history
from app.orchestration.job_models import QueueJob, QueueJobStatus, QueueJobType, QueueFailureRecord, QueueRetryRecord
from app.orchestration.retry_policy import calculate_retry_delay, classify_retryable_failure, should_retry
from app.persistence.repositories import QueueFailureRepository, QueueHistoryRepository, QueueJobRepository, QueueRetryRepository


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job_log_path() -> Path:
    return get_runtime_paths().manual_production_file("queue_jobs.jsonl")


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                records.append(payload)
    except Exception:
        return []
    return records


def _write_jsonl(path: Path, record: Dict[str, Any]) -> Dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return record


def _persist_latest(record: Dict[str, Any]) -> None:
    try:
        QueueJobRepository(jsonl_path=_job_log_path()).append_job(record)
    except Exception:
        pass


def _current_jobs(limit: int = 500) -> List[Dict[str, Any]]:
    records = _read_jsonl(_job_log_path())
    latest: Dict[str, Dict[str, Any]] = {}
    for record in records:
        job_id = str(record.get("job_id") or "")
        if job_id:
            latest[job_id] = record
    return list(latest.values())[: max(1, int(limit or 500))]


def _job_record(job: Dict[str, Any] | QueueJob) -> Dict[str, Any]:
    if isinstance(job, QueueJob):
        return job.to_jsonable_dict()
    return dict(job or {})


def enqueue_job(
    *,
    tender_id: str,
    job_type: QueueJobType | str,
    actor: str = "",
    operator: str = "",
    workflow_stage: str = "",
    payload: Optional[Dict[str, Any]] = None,
    max_attempts: int = 3,
) -> Dict[str, Any]:
    job = QueueJob.validate_payload(
        {
            "job_id": f"job-{uuid4().hex}",
            "tender_id": tender_id,
            "job_type": job_type,
            "status": QueueJobStatus.QUEUED,
            "actor": actor,
            "operator": operator,
            "workflow_stage": workflow_stage,
            "attempt_count": 0,
            "max_attempts": max_attempts,
            "payload": payload or {},
        }
    ).to_jsonable_dict()
    job["created_at"] = _now_iso()
    job["updated_at"] = job["created_at"]
    _write_jsonl(_job_log_path(), job)
    _persist_latest(job)
    append_history_event("enqueue", job)
    return job


def start_job(job_id: str, actor: str = "", operator: str = "") -> Dict[str, Any]:
    job = get_jobs_by_status(limit=1000, job_id=job_id)
    if not job:
        raise ValueError(f"Unknown job: {job_id}")
    current = dict(job[0])
    current["status"] = QueueJobStatus.RUNNING.value
    current["actor"] = actor or current.get("actor", "")
    current["operator"] = operator or current.get("operator", "")
    current["updated_at"] = _now_iso()
    _write_jsonl(_job_log_path(), current)
    _persist_latest(current)
    append_history_event("start", current)
    return current


def complete_job(job_id: str, actor: str = "", operator: str = "") -> Dict[str, Any]:
    job = get_jobs_by_status(limit=1000, job_id=job_id)
    if not job:
        raise ValueError(f"Unknown job: {job_id}")
    current = dict(job[0])
    current["status"] = QueueJobStatus.COMPLETED.value
    current["actor"] = actor or current.get("actor", "")
    current["operator"] = operator or current.get("operator", "")
    current["updated_at"] = _now_iso()
    _write_jsonl(_job_log_path(), current)
    _persist_latest(current)
    append_history_event("complete", current)
    return current


def fail_job(job_id: str, reason: str, actor: str = "", operator: str = "") -> Dict[str, Any]:
    job_list = get_jobs_by_status(limit=1000, job_id=job_id)
    if not job_list:
        raise ValueError(f"Unknown job: {job_id}")
    current = dict(job_list[0])
    current["status"] = QueueJobStatus.FAILED.value
    current["actor"] = actor or current.get("actor", "")
    current["operator"] = operator or current.get("operator", "")
    current["updated_at"] = _now_iso()
    current["failure_reason"] = reason
    _write_jsonl(_job_log_path(), current)
    _persist_latest(current)
    failure = QueueFailureRecord.validate_payload(
        {
            "job_id": job_id,
            "tender_id": current.get("tender_id", ""),
            "job_type": current.get("job_type", ""),
            "status": QueueJobStatus.FAILED,
            "actor": current.get("actor", ""),
            "operator": current.get("operator", ""),
            "reason": reason,
            "payload": current,
        }
    ).to_jsonable_dict()
    append_failure_history(failure)
    append_history_event("fail", current)
    return current


def block_job(job_id: str, reason: str = "", actor: str = "", operator: str = "") -> Dict[str, Any]:
    job_list = get_jobs_by_status(limit=1000, job_id=job_id)
    if not job_list:
        raise ValueError(f"Unknown job: {job_id}")
    current = dict(job_list[0])
    current["status"] = QueueJobStatus.BLOCKED.value
    current["actor"] = actor or current.get("actor", "")
    current["operator"] = operator or current.get("operator", "")
    current["updated_at"] = _now_iso()
    current["block_reason"] = reason
    _write_jsonl(_job_log_path(), current)
    _persist_latest(current)
    append_history_event("block", current)
    return current


def retry_job(job_id: str, reason: str = "", actor: str = "", operator: str = "") -> Dict[str, Any]:
    job_list = get_jobs_by_status(limit=1000, job_id=job_id)
    if not job_list:
        raise ValueError(f"Unknown job: {job_id}")
    current = dict(job_list[0])
    if not should_retry(current):
        raise ValueError(f"Job {job_id} is not eligible for retry")
    current["attempt_count"] = int(current.get("attempt_count", 0) or 0) + 1
    current["status"] = QueueJobStatus.RETRY_PENDING.value
    current["actor"] = actor or current.get("actor", "")
    current["operator"] = operator or current.get("operator", "")
    current["updated_at"] = _now_iso()
    delay_seconds = calculate_retry_delay(int(current["attempt_count"]))
    current["retry_delay_seconds"] = delay_seconds
    _write_jsonl(_job_log_path(), current)
    _persist_latest(current)
    retry = QueueRetryRecord.validate_payload(
        {
            "job_id": job_id,
            "tender_id": current.get("tender_id", ""),
            "job_type": current.get("job_type", ""),
            "attempt_count": current["attempt_count"],
            "delay_seconds": delay_seconds,
            "actor": current.get("actor", ""),
            "operator": current.get("operator", ""),
            "reason": reason,
            "payload": current,
        }
    ).to_jsonable_dict()
    append_retry_history(retry)
    append_history_event("retry", current)
    return current


def archive_job(job_id: str, actor: str = "", operator: str = "", reason: str = "") -> Dict[str, Any]:
    job_list = get_jobs_by_status(limit=1000, job_id=job_id)
    if not job_list:
        raise ValueError(f"Unknown job: {job_id}")
    current = dict(job_list[0])
    current["status"] = QueueJobStatus.ARCHIVED.value
    current["actor"] = actor or current.get("actor", "")
    current["operator"] = operator or current.get("operator", "")
    current["updated_at"] = _now_iso()
    current["archive_reason"] = reason
    _write_jsonl(_job_log_path(), current)
    _persist_latest(current)
    append_history_event("archive", current)
    return current


def get_jobs_by_status(
    *,
    status: QueueJobStatus | str | None = None,
    limit: int = 100,
    job_id: str = "",
) -> List[Dict[str, Any]]:
    current = _current_jobs(limit=limit)
    if job_id:
        current = [item for item in current if str(item.get("job_id") or "") == str(job_id)]
    if status is not None:
        status_value = status.value if isinstance(status, QueueJobStatus) else str(status)
        current = [item for item in current if str(item.get("status") or "") == status_value]
    return current[: max(1, int(limit or 100))]


def get_queue_snapshot(limit: int = 500) -> Dict[str, Any]:
    jobs = _current_jobs(limit=limit)
    by_status: Dict[str, int] = {}
    by_type: Dict[str, int] = {}
    for job in jobs:
        by_status[str(job.get("status") or "")] = by_status.get(str(job.get("status") or ""), 0) + 1
        by_type[str(job.get("job_type") or "")] = by_type.get(str(job.get("job_type") or ""), 0) + 1
    return {
        "status": "ok",
        "total_jobs": len(jobs),
        "by_status": by_status,
        "by_type": by_type,
        "jobs": jobs,
        "updated_at": _now_iso(),
    }
