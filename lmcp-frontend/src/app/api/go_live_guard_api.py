from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from app.services.go_live_guard_service import (
    clear_submission_lock,
    create_submission_lock,
    evaluate_pipeline_guard,
    get_guard_summary,
    has_submission_lock,
    is_rfq_rejected,
    is_source_paused,
)

router = APIRouter(prefix="/go-live-guards", tags=["go-live-guards"])


@router.get("/summary")
def guard_summary(limit: int = 80) -> Dict[str, Any]:
    return get_guard_summary(limit=limit)


@router.post("/evaluate")
def guard_evaluate(payload: Dict[str, Any]) -> Dict[str, Any]:
    return evaluate_pipeline_guard(payload)


@router.get("/is-rejected/{buyer_rfq_number}")
def guard_is_rejected(buyer_rfq_number: str) -> Dict[str, Any]:
    return {
        "status": "ok",
        "buyer_rfq_number": buyer_rfq_number,
        "rejected": is_rfq_rejected(buyer_rfq_number),
    }


@router.get("/is-source-paused/{source_name}")
def guard_is_source_paused(source_name: str) -> Dict[str, Any]:
    return {
        "status": "ok",
        "source_name": source_name,
        "paused": is_source_paused(source_name),
    }


@router.get("/has-submission-lock/{buyer_rfq_number}")
def guard_has_submission_lock(buyer_rfq_number: str, quote_number: str = "") -> Dict[str, Any]:
    return {
        "status": "ok",
        "buyer_rfq_number": buyer_rfq_number,
        "quote_number": quote_number,
        "locked": has_submission_lock(buyer_rfq_number, quote_number),
    }


@router.post("/submission-lock")
def guard_create_submission_lock(payload: Dict[str, Any]) -> Dict[str, Any]:
    item = create_submission_lock(
        buyer_rfq_number=payload.get("buyer_rfq_number") or "",
        quote_number=payload.get("quote_number") or "",
        reason=payload.get("reason") or "manual_lock",
        metadata=payload,
    )
    return {"status": "ok", "item": item}


@router.post("/clear-submission-lock")
def guard_clear_submission_lock(payload: Dict[str, Any]) -> Dict[str, Any]:
    return clear_submission_lock(
        buyer_rfq_number=payload.get("buyer_rfq_number") or "",
        quote_number=payload.get("quote_number") or "",
    )
