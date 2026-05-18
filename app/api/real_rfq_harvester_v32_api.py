from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body

from app.services.real_rfq_extractor_v32_service import extract_real_rfq_candidate, extract_real_rfqs
from app.services.real_rfq_harvester_v32_service import run_v32_real_rfq_harvest

router = APIRouter(prefix="/v32-real-rfq-harvester", tags=["V32 Real RFQ Harvester"])


@router.get("/status")
def status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": "V32_REAL_RFQ_HARVESTER_UPGRADE",
    }


@router.post("/classify")
def classify(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return extract_real_rfq_candidate(payload)


@router.post("/filter")
def filter_items(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    items = payload.get("items", [])
    return extract_real_rfqs(items)


@router.post("/run-once")
def run_once(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return run_v32_real_rfq_harvest(
        max_total=int(payload.get("max_total", 10)),
        max_per_source=int(payload.get("max_per_source", 1)),
        enable_auto_quote=bool(payload.get("enable_auto_quote", True)),
        persist_to_live_store=bool(payload.get("persist_to_live_store", True)),
        include_review_in_pipeline=bool(payload.get("include_review_in_pipeline", False)),
    )
