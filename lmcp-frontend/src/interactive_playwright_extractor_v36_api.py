from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body

from app.services.interactive_playwright_extractor_v36_service import (
    extract_interactive_portal,
    run_v36_interactive_extraction,
)

router = APIRouter(prefix="/v36-interactive-rfq", tags=["V36 Interactive Playwright RFQ Extractor"])


@router.get("/status")
def status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": "V36_INTERACTIVE_PLAYWRIGHT_EXTRACTOR",
    }


@router.post("/extract-portal")
def extract_portal(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return extract_interactive_portal(payload)


@router.post("/run-once")
def run_once(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return run_v36_interactive_extraction(
        max_portals=int(payload.get("max_portals", 1)),
        enable_auto_quote=bool(payload.get("enable_auto_quote", True)),
        persist_to_live_store=bool(payload.get("persist_to_live_store", True)),
        include_review_in_pipeline=bool(payload.get("include_review_in_pipeline", False)),
    )
