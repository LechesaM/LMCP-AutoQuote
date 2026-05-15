"""
LMCP V50.9.10 API - Tender Download Correlation
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter

from app.services.etenders_tender_download_correlation_v50_9_10 import (
    correlate_downloads,
    correlate_latest,
    get_v50_9_10_status,
)

router = APIRouter(
    prefix="/v50-9-10-tender-download-correlation",
    tags=["V50.9.10 Tender Download Correlation"],
)


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_v50_9_10_status()


@router.post("/correlate")
def correlate(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return correlate_downloads(payload or {})


@router.post("/latest")
def latest(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return correlate_latest(payload or {})
