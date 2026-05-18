"""
LMCP AutoQuote System
V41 Navigation Intelligence API

Routes:
- GET  /v41-navigation-intelligence/status
- POST /v41-navigation-intelligence/analyse-v40-json
- POST /v41-navigation-intelligence/analyse-pdf
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.navigation_intelligence_v41_service import (
    analyse_pdf_with_v40_then_v41,
    analyse_v40_json,
    get_navigation_intelligence_status,
)


router = APIRouter(
    prefix="/v41-navigation-intelligence",
    tags=["V41 Navigation Intelligence"],
)


class AnalyseV40JsonRequest(BaseModel):
    v40_json_path: str = Field(..., description="Path to the V40 output JSON.")
    buyer_rfq_number: Optional[str] = Field(None, description="Optional buyer RFQ number override.")
    output_dir: Optional[str] = Field(None, description="Optional V41 output directory.")


class AnalysePdfRequest(BaseModel):
    input_pdf: str = Field(..., description="Path to the tender/RFQ PDF, project-relative or absolute.")
    buyer_rfq_number: Optional[str] = Field(None, description="Optional buyer RFQ number.")
    max_pages_scan: int = Field(12, ge=1, le=80, description="Number of first pages V40 should scan for text navigation.")
    output_dir: Optional[str] = Field(None, description="Optional V41 output directory.")


@router.get("/status")
def status():
    return get_navigation_intelligence_status()


@router.post("/analyse-v40-json")
def analyse_v40_json_endpoint(payload: AnalyseV40JsonRequest):
    return analyse_v40_json(
        v40_json_path=payload.v40_json_path,
        buyer_rfq_number=payload.buyer_rfq_number,
        output_dir=payload.output_dir,
    )


@router.post("/analyse-pdf")
def analyse_pdf_endpoint(payload: AnalysePdfRequest):
    return analyse_pdf_with_v40_then_v41(
        input_pdf=payload.input_pdf,
        buyer_rfq_number=payload.buyer_rfq_number,
        max_pages_scan=payload.max_pages_scan,
        output_dir=payload.output_dir,
    )
