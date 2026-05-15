from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from app.services.pipeline_enforcement_service import (
    enforce_before_harvest_source,
    enforce_before_quote,
    enforce_before_rfq_processing,
    enforce_before_submission,
    get_enforcement_summary,
    mark_submission_completed,
)

router = APIRouter(prefix="/pipeline-enforcement", tags=["pipeline-enforcement"])


@router.get("/summary")
def enforcement_summary(limit: int = 100) -> Dict[str, Any]:
    return get_enforcement_summary(limit=limit)


@router.post("/before-quote")
async def before_quote(payload: Dict[str, Any]) -> Dict[str, Any]:
    return await enforce_before_quote(payload)


@router.post("/before-submission")
async def before_submission(payload: Dict[str, Any]) -> Dict[str, Any]:
    return await enforce_before_submission(payload)


@router.post("/before-harvest-source")
async def before_harvest_source(payload: Dict[str, Any]) -> Dict[str, Any]:
    return await enforce_before_harvest_source(payload)


@router.post("/before-rfq-processing")
async def before_rfq_processing(payload: Dict[str, Any]) -> Dict[str, Any]:
    return await enforce_before_rfq_processing(payload)


@router.post("/after-submission")
async def after_submission(payload: Dict[str, Any]) -> Dict[str, Any]:
    return await mark_submission_completed(payload)
