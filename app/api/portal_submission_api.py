from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from app.services.portal_submission_service import (
    auto_submit_portal,
    classify_submission_route,
    get_portal_submission_status,
    mark_portal_submission_proof,
    prepare_portal_submission,
    route_portal_submission,
)

router = APIRouter(prefix="/portal-submission", tags=["portal-submission"])


@router.get("/status")
def portal_submission_status(limit: int = 50) -> Dict[str, Any]:
    return get_portal_submission_status(limit=limit)


@router.post("/classify")
def portal_submission_classify(payload: Dict[str, Any]) -> Dict[str, Any]:
    return classify_submission_route(payload)


@router.post("/route")
def portal_submission_route(payload: Dict[str, Any]) -> Dict[str, Any]:
    return route_portal_submission(payload)


@router.post("/prepare")
async def portal_submission_prepare(payload: Dict[str, Any]) -> Dict[str, Any]:
    return await prepare_portal_submission(payload)


@router.post("/auto-submit")
async def portal_submission_auto_submit(payload: Dict[str, Any]) -> Dict[str, Any]:
    return await auto_submit_portal(payload)


@router.post("/submit")
async def portal_submission_submit_alias(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Compatibility alias for callers that use /portal-submission/submit.
    return await auto_submit_portal(payload)


@router.post("/proof")
async def portal_submission_proof(payload: Dict[str, Any]) -> Dict[str, Any]:
    return await mark_portal_submission_proof(payload)


@router.get("/health")
def portal_submission_health() -> Dict[str, Any]:
    status = get_portal_submission_status(limit=5)
    return {
        "status": "ok",
        "service": "portal-submission",
        "available_endpoints": {
            "status": "/portal-submission/status",
            "classify": "/portal-submission/classify",
            "route": "/portal-submission/route",
            "prepare": "/portal-submission/prepare",
            "auto_submit": "/portal-submission/auto-submit",
            "submit_alias": "/portal-submission/submit",
            "proof": "/portal-submission/proof",
        },
        "summary": status.get("summary", {}),
    }
