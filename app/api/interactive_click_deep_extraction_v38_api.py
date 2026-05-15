
from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, Body

from app.services.interactive_click_deep_extraction_v38_service import (
    deep_click_extract_candidate,
    run_v38_from_v36,
)

router = APIRouter(prefix="/v38-click-deep-rfq", tags=["V38 Interactive Click Deep RFQ Extraction"])

@router.get("/status")
def status() -> Dict[str, Any]:
    return {"status": "ok", "service_version": "V38_INTERACTIVE_CLICK_DEEP_EXTRACTION"}

@router.post("/enrich-one")
def enrich_one(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return deep_click_extract_candidate(payload)

@router.post("/run-from-v36")
def run_from_v36(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return run_v38_from_v36(
        max_portals=int(payload.get("max_portals", 1)),
        enable_auto_quote=bool(payload.get("enable_auto_quote", False)),
        persist_to_live_store=bool(payload.get("persist_to_live_store", True)),
        include_review=bool(payload.get("include_review", False)),
    )
