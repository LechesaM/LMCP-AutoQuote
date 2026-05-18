
from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, Body

from app.services.true_navigation_extraction_v39_service import (
    true_navigation_extract_candidate,
    run_v39_from_v36,
)

router = APIRouter(prefix="/v39-true-navigation", tags=["V39 True Navigation Extraction"])

@router.get("/status")
def status() -> Dict[str, Any]:
    return {"status": "ok", "service_version": "V39_TRUE_NAVIGATION_EXTRACTION_ENGINE"}

@router.post("/enrich-one")
def enrich_one(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return true_navigation_extract_candidate(payload)

@router.post("/run-from-v36")
def run_from_v36(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return run_v39_from_v36(
        max_portals=int(payload.get("max_portals", 1)),
        enable_auto_quote=bool(payload.get("enable_auto_quote", False)),
        persist_to_live_store=bool(payload.get("persist_to_live_store", True)),
        include_review=bool(payload.get("include_review", False)),
    )
