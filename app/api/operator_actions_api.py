from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from app.services.operator_action_service import (
    force_quote,
    get_operator_action_summary,
    mark_review_complete,
    pause_source,
    reject_opportunity,
    retry_submission,
)

router = APIRouter(prefix="/operator-actions", tags=["operator-actions"])


@router.get("/summary")
def operator_summary(limit: int = 30) -> Dict[str, Any]:
    return get_operator_action_summary(limit=limit)


@router.post("/force-quote")
async def operator_force_quote(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = await force_quote(payload)
    return {"status": "ok", "message": result.get("message"), "item": result}


@router.post("/retry-submission")
async def operator_retry_submission(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = await retry_submission(payload)
    return {"status": "ok", "message": result.get("message"), "item": result}


@router.post("/reject-opportunity")
async def operator_reject_opportunity(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = await reject_opportunity(payload)
    return {"status": "ok", "message": result.get("message"), "item": result}


@router.post("/mark-review-complete")
async def operator_mark_review_complete(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = await mark_review_complete(payload)
    return {"status": "ok", "message": result.get("message"), "item": result}


@router.post("/pause-source")
async def operator_pause_source(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = await pause_source(payload)
    return {"status": "ok", "message": result.get("message"), "item": result}

@router.get("/is-rejected/{buyer_rfq_number}")
def operator_is_rejected(buyer_rfq_number: str) -> Dict[str, Any]:
    from app.services.operator_action_service import is_opportunity_rejected
    return {
        "status": "ok",
        "buyer_rfq_number": buyer_rfq_number,
        "rejected": is_opportunity_rejected(buyer_rfq_number),
    }


@router.get("/is-source-paused/{source_name}")
def operator_is_source_paused(source_name: str) -> Dict[str, Any]:
    from app.services.operator_action_service import is_source_paused
    return {
        "status": "ok",
        "source_name": source_name,
        "paused": is_source_paused(source_name),
    }
