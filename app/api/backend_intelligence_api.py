"""
API router for LMCP Backend Intelligence Layer.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Query

from app.services.backend_intelligence_layer import (
    SERVICE_VERSION,
    analyze_single_opportunity,
    build_demo_records,
    intelligent_filter_opportunities,
    utc_now_iso,
)

router = APIRouter(prefix="/backend-intelligence", tags=["Backend Intelligence"])


@router.get("/status")
def status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "updated_at": utc_now_iso(),
        "message": "Backend intelligence layer is active.",
    }


@router.post("/analyze")
def analyze(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    return analyze_single_opportunity(payload)


@router.post("/filter")
def filter_opportunities(
    payload: Dict[str, Any] = Body(...),
    limit: int = Query(50, ge=1, le=500),
    include_rejected: bool = Query(False),
) -> Dict[str, Any]:
    opportunities = payload.get("opportunities") or payload.get("items") or payload.get("records") or []
    return intelligent_filter_opportunities(
        opportunities,
        limit=limit,
        include_rejected=include_rejected,
    )


@router.get("/demo")
def demo(include_rejected: bool = Query(True)) -> Dict[str, Any]:
    return intelligent_filter_opportunities(
        build_demo_records(),
        limit=20,
        include_rejected=include_rejected,
    )
