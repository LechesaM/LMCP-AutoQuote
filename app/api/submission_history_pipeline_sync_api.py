from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.submission_history_pipeline_sync_service import (
    get_synced_submission_history,
    sync_submission_history_from_pipeline_logs,
)

router = APIRouter(
    prefix="/submission-history",
    tags=["Submission History"],
)


@router.post("/sync")
def sync_submission_history(limit: int = Query(default=500, ge=1, le=5000)):
    return sync_submission_history_from_pipeline_logs(limit=limit)


@router.get("/recent-real")
def get_recent_real_submission_history(limit: int = Query(default=20, ge=1, le=100)):
    return get_synced_submission_history(limit=limit)
