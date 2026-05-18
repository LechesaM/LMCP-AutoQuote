from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body

from app.services.smart_harvester_v31_service import run_smart_national_tender_radar
from app.services.smart_rfq_detection_service import apply_smart_rfq_detection, classify_rfq

router = APIRouter(prefix="/v31-smart-harvester", tags=["V31 Smart Harvester"])


@router.get("/status")
def status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": "V31_SMART_HARVESTER_REAL_RFQ_DETECTION",
    }


@router.post("/classify")
def classify(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return classify_rfq(payload)


@router.post("/apply")
def apply(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return apply_smart_rfq_detection(payload)


@router.post("/run-once")
def run_once(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return run_smart_national_tender_radar(
        max_total=int(payload.get("max_total", 10)),
        max_per_source=int(payload.get("max_per_source", 1)),
        enable_auto_quote=bool(payload.get("enable_auto_quote", True)),
        persist_to_live_store=bool(payload.get("persist_to_live_store", True)),
    )


@router.post("/multi-portal-discovery")
def multi_portal_discovery(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    from app.services.tender_harvester import run_multi_portal_discovery

    return run_multi_portal_discovery(
        max_sources=int(payload.get("max_sources", 12)),
        max_per_source=int(payload.get("max_per_source", 4)),
        headless=bool(payload.get("headless", True)),
        include_bad_sources=bool(payload.get("include_bad_sources", False)),
        dry_run=bool(payload.get("dry_run", True)),
        source_pack_mode=payload.get("source_pack_mode") or payload.get("pack_mode"),
        buyer_intelligence=bool(payload.get("buyer_intelligence", True)),
        opportunity_forecasting=bool(payload.get("opportunity_forecasting", True)),
        forecast_watchlist=bool(payload.get("forecast_watchlist", payload.get("action_watchlist", True))),
    )


@router.post("/run-radar-cycle")
def run_radar_cycle(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    from app.services.tender_harvester import run_autonomous_radar_cycle

    return run_autonomous_radar_cycle(
        cycles=int(payload.get("cycles", 1)),
        max_sources=int(payload.get("max_sources", 3)),
        max_per_source=int(payload.get("max_per_source", 1)),
        headless=bool(payload.get("headless", True)),
        include_bad_sources=bool(payload.get("include_bad_sources", False)),
        source_pack_mode=payload.get("source_pack_mode") or payload.get("pack_mode"),
    )


@router.post("/extract-real-opportunities")
def extract_real_opportunities(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    from app.services.tender_harvester import run_real_opportunity_extraction

    return run_real_opportunity_extraction(
        max_sources=int(payload.get("max_sources", 3)),
        max_per_source=int(payload.get("max_per_source", 1)),
        headless=bool(payload.get("headless", True)),
        include_bad_sources=bool(payload.get("include_bad_sources", False)),
        source_pack_mode=payload.get("source_pack_mode") or payload.get("pack_mode"),
    )


@router.post("/document-intelligence-dry-run")
def document_intelligence_dry_run(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    from app.services.tender_harvester import run_document_intelligence_dry_run

    return run_document_intelligence_dry_run(
        max_sources=int(payload.get("max_sources", 3)),
        max_per_source=int(payload.get("max_per_source", 1)),
        headless=bool(payload.get("headless", True)),
        include_bad_sources=bool(payload.get("include_bad_sources", False)),
        source_pack_mode=payload.get("source_pack_mode") or payload.get("pack_mode"),
    )


@router.post("/review-queue-dry-run")
def review_queue_dry_run(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    from app.services.tender_harvester import run_review_queue_dry_run

    return run_review_queue_dry_run(
        max_sources=int(payload.get("max_sources", 3)),
        max_per_source=int(payload.get("max_per_source", 1)),
        headless=bool(payload.get("headless", True)),
        include_bad_sources=bool(payload.get("include_bad_sources", False)),
        source_pack_mode=payload.get("source_pack_mode") or payload.get("pack_mode"),
    )


@router.get("/review-queue/status")
def review_queue_status() -> Dict[str, Any]:
    from app.services.tender_harvester import get_review_queue_status

    return get_review_queue_status()
