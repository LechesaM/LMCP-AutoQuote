from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body

from app.services.structured_rfq_extractor_v34_service import (
    extract_structured_portal,
    run_v34_structured_extraction,
)

router = APIRouter(prefix="/v34-structured-rfq", tags=["V34 Structured RFQ Extractor"])


@router.get("/status")
def status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": "V34_STRUCTURED_RFQ_EXTRACTOR",
    }


@router.post("/extract-portal")
def extract_portal(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return extract_structured_portal(payload)


@router.post("/run-once")
def run_once(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return run_v34_structured_extraction(
        max_portals=int(payload.get("max_portals", 3)),
        enable_auto_quote=bool(payload.get("enable_auto_quote", True)),
        persist_to_live_store=bool(payload.get("persist_to_live_store", True)),
        include_review_in_pipeline=bool(payload.get("include_review_in_pipeline", False)),
    )
