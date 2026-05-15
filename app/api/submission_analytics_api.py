from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Query

from app.services.submission_analytics_service import (
    get_submission_profit_tracking,
    get_submission_success_and_profit_summary,
    get_submission_success_tracking,
)

router = APIRouter(prefix="/submission-analytics", tags=["submission-analytics"])


@router.get("/success")
def submission_success_tracking() -> Dict[str, Any]:
    return get_submission_success_tracking()


@router.get("/profit")
def submission_profit_tracking(submitted_only: bool = Query(default=True)) -> Dict[str, Any]:
    return get_submission_profit_tracking(submitted_only=submitted_only)


@router.get("/summary")
def submission_success_and_profit_summary() -> Dict[str, Any]:
    return get_submission_success_and_profit_summary()


