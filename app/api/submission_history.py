from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.submission_history_service import (
    get_submission_history_by_rfq,
    get_submission_history_item,
    get_submission_summary,
    list_submission_history,
)

router = APIRouter(prefix="/submission-history", tags=["submission-history"])


@router.get("")
def read_submission_history(
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None, description="queued | submitted | failed | manual_action_required"),
    buyer_name: Optional[str] = Query(default=None),
    rfq_number: Optional[str] = Query(default=None),
    quote_number: Optional[str] = Query(default=None),
    submission_method: Optional[str] = Query(default=None),
):
    result = list_submission_history(
        limit=limit,
        offset=offset,
        status=status,
        buyer_name=buyer_name,
        buyer_rfq_number=rfq_number,
        quote_number=quote_number,
        submission_method=submission_method,
    )

    return {
        "count": int(result.get("total") or 0),
        "limit": int(result.get("limit") or limit),
        "offset": int(result.get("offset") or offset),
        "items": result.get("items") if isinstance(result.get("items"), list) else [],
    }


@router.get("/summary")
def read_submission_history_summary():
    return get_submission_summary()


@router.get("/rfq/{rfq_number}")
def read_submission_by_rfq(rfq_number: str):
    items = get_submission_history_by_rfq(rfq_number)
    return {
        "found": len(items) > 0,
        "count": len(items),
        "items": items,
    }


@router.get("/{history_id}")
def read_submission_history_item(history_id: str):
    item = get_submission_history_item(history_id)
    if not item:
        raise HTTPException(status_code=404, detail="Submission history item not found")
    return item


