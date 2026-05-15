from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.pricing_table_extraction_v42_service import (
    analyse_pdf_with_v41_then_v42,
    extract_pricing_from_v41_json,
    extract_pricing_tables_from_pdf,
    get_pricing_table_extraction_status,
)

router = APIRouter(
    prefix="/v42-pricing-table-extraction",
    tags=["V42 Pricing Table Extraction"],
)


class ExtractPdfRequest(BaseModel):
    input_pdf: str = Field(..., description="Path to the tender/RFQ PDF.")
    buyer_rfq_number: Optional[str] = None
    pages: Optional[List[int]] = None
    v41_json_path: Optional[str] = None
    output_dir: Optional[str] = None
    min_confidence: float = Field(0.45, ge=0.0, le=1.0)


class ExtractFromV41JsonRequest(BaseModel):
    v41_json_path: str
    input_pdf: Optional[str] = None
    output_dir: Optional[str] = None
    min_confidence: float = Field(0.45, ge=0.0, le=1.0)


class AnalysePdfRequest(BaseModel):
    input_pdf: str
    buyer_rfq_number: Optional[str] = None
    max_pages_scan: int = Field(25, ge=1, le=100)
    output_dir: Optional[str] = None
    min_confidence: float = Field(0.45, ge=0.0, le=1.0)


@router.get("/status")
def status():
    return get_pricing_table_extraction_status()


@router.post("/extract-pdf")
def extract_pdf(payload: ExtractPdfRequest):
    return extract_pricing_tables_from_pdf(
        input_pdf=payload.input_pdf,
        buyer_rfq_number=payload.buyer_rfq_number,
        pages=payload.pages,
        v41_json_path=payload.v41_json_path,
        output_dir=payload.output_dir,
        min_confidence=payload.min_confidence,
    )


@router.post("/extract-from-v41-json")
def extract_from_v41_json(payload: ExtractFromV41JsonRequest):
    return extract_pricing_from_v41_json(
        v41_json_path=payload.v41_json_path,
        input_pdf=payload.input_pdf,
        output_dir=payload.output_dir,
        min_confidence=payload.min_confidence,
    )


@router.post("/analyse-pdf")
def analyse_pdf(payload: AnalysePdfRequest):
    return analyse_pdf_with_v41_then_v42(
        input_pdf=payload.input_pdf,
        buyer_rfq_number=payload.buyer_rfq_number,
        max_pages_scan=payload.max_pages_scan,
        output_dir=payload.output_dir,
        min_confidence=payload.min_confidence,
    )
