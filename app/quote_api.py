from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.quote_engine import build_priced_items, build_quote_text
from app.quote_store import get_quote, list_quotes, save_quote
from app.storage import list_opportunities

router = APIRouter(tags=["quotes"])


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _next_quote_number() -> str:
    prefix = os.getenv("QUOTE_PREFIX", "LMCP-Q")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{stamp}"


class QuoteItem(BaseModel):
    description: str
    qty: float = 1.0
    unit: str = "Lot"
    rate: float = 0.0


class QuoteGenerateRequest(BaseModel):
    # choose opportunity by index from Redis list
    opportunity_index: int = Field(0, ge=0)

    # optional client details
    client_email: Optional[str] = None
    contact_person: Optional[str] = None

    # pricing controls
    profit_percent: float = Field(20.0, ge=0.0, le=200.0)
    vat_percent: float = Field(15.0, ge=0.0, le=30.0)

    # ✅ smart pricing override (optional)
    # If you know the budget/value, supply it here and it will price from it.
    base_amount: Optional[float] = Field(None, ge=0.0)

    # If provided, replaces smart-priced items
    items: Optional[List[QuoteItem]] = None

    validity_days: int = Field(30, ge=1, le=365)
    lead_time_days: int = Field(14, ge=0, le=365)


@router.post("/quote/generate")
def generate_quote(req: QuoteGenerateRequest) -> Dict[str, Any]:
    ops = list_opportunities()
    if not ops:
        raise HTTPException(status_code=404, detail="No opportunities found. Run /poll/run first.")

    if req.opportunity_index >= len(ops):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid opportunity_index. You have {len(ops)} opportunities (0..{len(ops)-1}).",
        )

    op = ops[req.opportunity_index]
    quote_number = _next_quote_number()

    # ✅ SMART PRICING DEFAULT
    scope, base_used, smart_items = build_priced_items(op, base_amount=req.base_amount)

    # Allow manual items override if user provides them
    if req.items and len(req.items) > 0:
        items = [i.model_dump() for i in req.items]
        base_used_for_display = req.base_amount
    else:
        items = smart_items
        base_used_for_display = base_used

    quote_text, meta = build_quote_text(
        op,
        quote_number=quote_number,
        client_email=req.client_email,
        contact_person=req.contact_person,
        items=items,
        profit_percent=req.profit_percent,
        vat_percent=req.vat_percent,
        validity_days=req.validity_days,
        lead_time_days=req.lead_time_days,
        base_amount_used=base_used_for_display,
    )

    quote_obj = {
        "quote_number": quote_number,
        "created_at": _utc_now(),
        "opportunity_index": req.opportunity_index,
        "opportunity": op,
        "meta": meta,
        "items": items,
        "quote_text": quote_text,
        "status": "draft",
        "pricing": {"scope": scope, "base_amount_used": base_used_for_display},
    }

    quote_id = save_quote(quote_obj)
    return {
        "quote_id": quote_id,
        "quote_number": quote_number,
        "status": "draft",
        "scope": scope,
        "base_amount_used": base_used_for_display,
    }


@router.get("/quote/{quote_id}")
def read_quote(quote_id: str) -> Dict[str, Any]:
    q = get_quote(quote_id)
    if not q:
        raise HTTPException(status_code=404, detail="Quote not found")
    return q


@router.get("/quote/list")
def read_quote_list(limit: int = 50) -> Dict[str, Any]:
    return {"quotes": list_quotes(limit=limit)}
