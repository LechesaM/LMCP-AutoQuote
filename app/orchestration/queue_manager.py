from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

from app.core.runtime_paths import get_runtime_paths
from app.orchestration import job_history
from app.orchestration import retry_policy
from app.orchestration.job_models import QueueJobStatus
from app.persistence import db as persistence_db
from app.persistence.repositories import record_persistence_write_success


_JOBS: Dict[str, Dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _history_file() -> Path:
    return get_runtime_paths().manual_production_dir / "queue_history.jsonl"


def _write_history(item: Dict[str, Any]) -> None:
    path = _history_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, default=str) + "\n")
    try:
        with persistence_db.connection_scope() as connection:
            connection.execute("INSERT INTO queue_history_records (payload_json) VALUES (?)", (json.dumps(item, default=str),))
            connection.execute("INSERT INTO queue_job_records (payload_json) VALUES (?)", (json.dumps(item, default=str),))
            connection.commit()
            record_persistence_write_success()
    except Exception:
        pass


def enqueue_job(*, tender_id: str, job_type: Any, actor: str, operator: str, workflow_stage: str, payload: Dict[str, Any], max_attempts: int = 3) -> Dict[str, Any]:
    job_id = str(uuid4())
    job_type_value = getattr(job_type, "value", str(job_type))
    job = {"job_id": job_id, "tender_id": tender_id, "job_type": job_type_value, "status": QueueJobStatus.PENDING.value, "attempts": 0, "max_attempts": max_attempts, "updated_at": _now_iso(), "payload": payload}
    _JOBS[job_id] = job
    _write_history(job)
    job_history.append(job_id, job)
    return job


def _update(job_id: str, status: QueueJobStatus) -> Dict[str, Any]:
    job = _JOBS[job_id]
    job["status"] = status.value
    job["updated_at"] = _now_iso()
    _write_history(job)
    job_history.append(job_id, job)
    return dict(job)


def start_job(job_id: str, actor: str, operator: str) -> Dict[str, Any]:
    return _update(job_id, QueueJobStatus.RUNNING)


def complete_job(job_id: str, actor: str, operator: str) -> Dict[str, Any]:
    return _update(job_id, QueueJobStatus.COMPLETED)


def fail_job(job_id: str, reason: str, actor: str, operator: str) -> Dict[str, Any]:
    return _update(job_id, QueueJobStatus.FAILED)


def retry_job(job_id: str, reason: str, actor: str, operator: str) -> Dict[str, Any]:
    job = _JOBS[job_id]
    if int(job.get("attempts", 0)) >= int(job.get("max_attempts", 1)):
        raise ValueError("max attempts reached")
    if not retry_policy.should_retry(job):
        raise ValueError("retry not allowed")
    job["attempts"] = int(job.get("attempts", 0)) + 1
    return _update(job_id, QueueJobStatus.RETRY_PENDING)


def block_job(job_id: str, reason: str, actor: str, operator: str) -> Dict[str, Any]:
    return _update(job_id, QueueJobStatus.BLOCKED)


def get_jobs_by_status(status: QueueJobStatus | None = None, job_id: str | None = None, limit: int = 500) -> List[Dict[str, Any]]:
    items = list(_JOBS.values())
    if job_id:
        items = [item for item in items if item["job_id"] == job_id]
    if status:
        items = [item for item in items if item["status"] == status.value]
    return items[:limit]
