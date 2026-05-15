"""
LMCP AutoQuote System
V40 Clickable Navigation Extractor API

Routes:
- GET  /v40-clickable-navigation/status
- POST /v40-clickable-navigation/extract
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.clickable_navigation_v40_service import (
    SERVICE_VERSION,
    extract_clickable_navigation,
    get_clickable_navigation_status,
)


router = APIRouter(prefix="/v40-clickable-navigation", tags=["V40 Clickable Navigation Extractor"])


class ClickableNavigationExtractRequest(BaseModel):
    input_pdf: str = Field(..., description="Path to the tender/RFQ PDF, project-relative or absolute.")
    buyer_rfq_number: Optional[str] = Field(None, description="Optional buyer RFQ number used in output file naming.")
    output_dir: Optional[str] = Field(None, description="Optional output directory. Defaults to runtime/clickable_navigation_v40.")
    max_pages_scan: int = Field(8, ge=1, le=50, description="Number of first pages to scan for text navigation candidates.")
    include_low_confidence: bool = Field(True, description="Return lower-confidence text candidates as well as real PDF links.")


@router.get("/status")
def status():
    return get_clickable_navigation_status()


@router.post("/extract")
def extract(payload: ClickableNavigationExtractRequest):
    return extract_clickable_navigation(
        input_pdf=payload.input_pdf,
        buyer_rfq_number=payload.buyer_rfq_number,
        output_dir=payload.output_dir,
        max_pages_scan=payload.max_pages_scan,
        include_low_confidence=payload.include_low_confidence,
    )
