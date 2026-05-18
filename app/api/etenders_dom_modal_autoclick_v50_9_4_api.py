"""
LMCP V50.9.4 API - DOM + Modal Auto-Dismiss + Attachment Auto-Click
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter

from app.services.etenders_dom_modal_autoclick_v50_9_4_service import (
    capture_dom_modal_autoclick,
    get_v50_9_4_status,
)

router = APIRouter(
    prefix="/v50-9-4-dom-modal-autoclick",
    tags=["V50.9.4 eTenders DOM Modal AutoClick"],
)


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_v50_9_4_status()


@router.post("/capture")
def capture(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return capture_dom_modal_autoclick(payload or {})
