
from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, Body
from app.services.deep_rfq_link_extractor_v37_service import enrich_rfq_candidate, enrich_rfq_candidates, run_v37_from_v36

router = APIRouter(prefix="/v37-deep-rfq", tags=["V37 Deep RFQ Link Extractor"])

@router.get("/status")
def status() -> Dict[str, Any]:
    return {"status": "ok", "service_version": "V37_DEEP_RFQ_LINK_EXTRACTOR"}

@router.post("/enrich-one")
def enrich_one(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return enrich_rfq_candidate(payload)

@router.post("/enrich-many")
def enrich_many(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return enrich_rfq_candidates(payload.get("items", []))

@router.post("/run-from-v36")
def run_from_v36(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return run_v37_from_v36(
        max_portals=int(payload.get("max_portals", 1)),
        enable_auto_quote=bool(payload.get("enable_auto_quote", False)),
        persist_to_live_store=bool(payload.get("persist_to_live_store", True)),
        include_review=bool(payload.get("include_review", True)),
    )
