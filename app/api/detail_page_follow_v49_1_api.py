from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from app.services.detail_page_follow_v49_1_service import (
    follow_detail_pages,
    get_v49_1_status,
)

router = APIRouter(
    prefix="/v49-1-detail-page-follow",
    tags=["V49.1 Detail Page Follow"],
)


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_v49_1_status()


@router.post("/follow")
def follow(payload: Dict[str, Any]) -> Dict[str, Any]:
    return follow_detail_pages(payload)
