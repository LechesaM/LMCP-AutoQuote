from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body

from app.services.playwright_live_dom_extractor_v35_service import (
    extract_live_dom_portal,
    run_v35_live_dom_extraction,
)

router = APIRouter(prefix="/v35-playwright-rfq", tags=["V35 Playwright RFQ Extractor"])


@router.get("/status")
def status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": "V35_PLAYWRIGHT_LIVE_DOM_EXTRACTOR",
    }


@router.post("/extract-portal")
def extract_portal(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return extract_live_dom_portal(payload)


@router.post("/run-once")
def run_once(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return run_v35_live_dom_extraction(
        max_portals=int(payload.get("max_portals", 3)),
        enable_auto_quote=bool(payload.get("enable_auto_quote", True)),
        persist_to_live_store=bool(payload.get("persist_to_live_store", True)),
        include_review_in_pipeline=bool(payload.get("include_review_in_pipeline", False)),
    )
