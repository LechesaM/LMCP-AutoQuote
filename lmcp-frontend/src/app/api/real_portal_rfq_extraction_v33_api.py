from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body

from app.services.real_portal_rfq_extraction_v33_service import (
    extract_portal_rfqs,
    run_v33_real_portal_extraction,
)

router = APIRouter(prefix="/v33-real-portal-rfq", tags=["V33 Real Portal RFQ Extraction"])


@router.get("/status")
def status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": "V33_REAL_PORTAL_RFQ_EXTRACTION_ENGINE",
    }


@router.post("/extract-portal")
def extract_portal(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return extract_portal_rfqs(payload)


@router.post("/run-once")
def run_once(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return run_v33_real_portal_extraction(
        max_portals=int(payload.get("max_portals", 4)),
        enable_auto_quote=bool(payload.get("enable_auto_quote", True)),
        persist_to_live_store=bool(payload.get("persist_to_live_store", True)),
        include_review_in_pipeline=bool(payload.get("include_review_in_pipeline", False)),
    )
