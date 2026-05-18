"""
LMCP V50.9.5 API - DOM Trigger + Forced Click Injection
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter

from app.services.etenders_dom_trigger_forced_click_v50_9_5_service import (
    capture_dom_trigger_forced_click,
    get_v50_9_5_status,
)

router = APIRouter(
    prefix="/v50-9-5-dom-trigger-forced-click",
    tags=["V50.9.5 eTenders DOM Trigger Forced Click"],
)


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_v50_9_5_status()


@router.post("/capture")
def capture(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return capture_dom_trigger_forced_click(payload or {})
