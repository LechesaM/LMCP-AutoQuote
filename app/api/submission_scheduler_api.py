from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Query

from app.services.submission_scheduler_service import (
    get_submission_scheduler_health,
    get_submission_scheduler_last_run,
    run_submission_retry_cycle,
)
from app.tasks.submission_scheduler_tasks import run_submission_retry_cycle_task

router = APIRouter(prefix="/submission-scheduler", tags=["submission-scheduler"])


@router.get("/health")
def submission_scheduler_health() -> Dict[str, Any]:
    return get_submission_scheduler_health()


@router.get("/last-run")
def submission_scheduler_last_run() -> Dict[str, Any]:
    return get_submission_scheduler_last_run()


@router.post("/run-now")
def submission_scheduler_run_now(limit: int = Query(default=10, ge=1, le=100)) -> Dict[str, Any]:
    return run_submission_retry_cycle(limit=limit)


@router.post("/enqueue")
def submission_scheduler_enqueue(limit: Optional[int] = Query(default=None, ge=1, le=100)) -> Dict[str, Any]:
    task = run_submission_retry_cycle_task.delay(limit=limit)
    return {
        "status": "queued",
        "task_id": task.id,
        "limit": limit,
    }


