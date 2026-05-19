from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.services.operator_action_service import (
    force_quote,
    get_operator_action_summary,
    mark_review_complete,
    pause_source,
    reject_opportunity,
    retry_submission,
)
from app.auth.auth_service import require_permission, require_role

router = APIRouter(prefix="/operator-actions", tags=["operator-actions"])


@router.get("/summary", dependencies=[Depends(require_permission("view_operator_queue"))])
def operator_summary(limit: int = 30) -> Dict[str, Any]:
    return get_operator_action_summary(limit=limit)


@router.post("/force-quote", dependencies=[Depends(require_role("supervisor"))])
async def operator_force_quote(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = await force_quote(payload)
    return {"status": "ok", "message": result.get("message"), "item": result}


@router.post("/retry-submission", dependencies=[Depends(require_role("supervisor"))])
async def operator_retry_submission(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = await retry_submission(payload)
    return {"status": "ok", "message": result.get("message"), "item": result}


@router.post("/reject-opportunity", dependencies=[Depends(require_role("supervisor"))])
async def operator_reject_opportunity(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = await reject_opportunity(payload)
    return {"status": "ok", "message": result.get("message"), "item": result}


@router.post("/mark-review-complete", dependencies=[Depends(require_permission("mark_reviewed"))])
async def operator_mark_review_complete(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = await mark_review_complete(payload)
    return {"status": "ok", "message": result.get("message"), "item": result}


@router.post("/pause-source", dependencies=[Depends(require_permission("manage_sources"))])
async def operator_pause_source(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = await pause_source(payload)
    return {"status": "ok", "message": result.get("message"), "item": result}

@router.get("/is-rejected/{buyer_rfq_number}", dependencies=[Depends(require_permission("view_operator_queue"))])
def operator_is_rejected(buyer_rfq_number: str) -> Dict[str, Any]:
    from app.services.operator_action_service import is_opportunity_rejected
    return {
        "status": "ok",
        "buyer_rfq_number": buyer_rfq_number,
        "rejected": is_opportunity_rejected(buyer_rfq_number),
    }


@router.get("/is-source-paused/{source_name}", dependencies=[Depends(require_permission("manage_sources"))])
def operator_is_source_paused(source_name: str) -> Dict[str, Any]:
    from app.services.operator_action_service import is_source_paused
    return {
        "status": "ok",
        "source_name": source_name,
        "paused": is_source_paused(source_name),
    }
