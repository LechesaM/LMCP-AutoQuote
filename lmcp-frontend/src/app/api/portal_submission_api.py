from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from app.services.portal_submission_service import (
    classify_submission_route,
    get_portal_submission_status,
    mark_portal_submission_proof,
    prepare_portal_submission,
)

router = APIRouter(prefix="/portal-submission", tags=["portal-submission"])


@router.get("/status")
def portal_submission_status(limit: int = 50) -> Dict[str, Any]:
    return get_portal_submission_status(limit=limit)


@router.post("/classify")
def portal_submission_classify(payload: Dict[str, Any]) -> Dict[str, Any]:
    return classify_submission_route(payload)


@router.post("/prepare")
async def portal_submission_prepare(payload: Dict[str, Any]) -> Dict[str, Any]:
    return await prepare_portal_submission(payload)


@router.post("/proof")
async def portal_submission_proof(payload: Dict[str, Any]) -> Dict[str, Any]:
    return await mark_portal_submission_proof(payload)
