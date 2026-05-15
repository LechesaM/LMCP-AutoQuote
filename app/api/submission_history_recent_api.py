# app/api/submission_history_recent_api.py

from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.submission_history_recent_service import load_recent_submission_history


router = APIRouter(
    prefix="/submission-history",
    tags=["Submission History"],
)


@router.get("/recent")
def get_recent_submission_history(limit: int = Query(default=20, ge=1, le=100)):
    return load_recent_submission_history(limit=limit)
