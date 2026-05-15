from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from app.services.real_rfq_detail_navigation_v49_service import (
    analyse_rfq_detail_navigation,
    get_v49_status,
)

router = APIRouter(prefix="/v49-real-rfq-detail-navigation", tags=["V49 Real RFQ Detail Navigation"])


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_v49_status()


@router.post("/analyse")
def analyse(payload: Dict[str, Any]) -> Dict[str, Any]:
    return analyse_rfq_detail_navigation(payload)
