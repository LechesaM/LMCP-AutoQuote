from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, Query

from app.services.real_profit_pricing_service import (
    enrich_with_real_profit_pricing,
    get_real_profit_pricing_status,
)

router = APIRouter(prefix="/real-profit-pricing", tags=["real-profit-pricing"])


@router.get("/status")
def status(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    return get_real_profit_pricing_status(limit=limit)


@router.post("/price")
def price(payload: Dict[str, Any]) -> Dict[str, Any]:
    return enrich_with_real_profit_pricing(payload)
