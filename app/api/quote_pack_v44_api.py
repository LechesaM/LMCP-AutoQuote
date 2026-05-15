from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.quote_pack_v44_service import (
    generate_quote_pack_from_pdf,
    generate_quote_pack_from_v43_json,
    get_quote_pack_v44_status,
)

router = APIRouter(prefix="/v44-quote-pack", tags=["V44 Quote Pack Generator"])


class GenerateFromPdfRequest(BaseModel):
    input_pdf: str
    buyer_rfq_number: Optional[str] = None
    company_name: str = "Lechesa Manaba Consulting and Projects (Pty) Ltd"
    output_dir: Optional[str] = None
    margin_percent: float = Field(25.0, ge=1.0, le=90.0)
    minimum_profit_required: float = Field(30000.0, ge=0.0)
    apply_profit_floor: bool = True
    min_confidence: float = Field(0.35, ge=0.0, le=1.0)
    compliance_files: Optional[List[str]] = None


class GenerateFromV43JsonRequest(BaseModel):
    v43_json_path: str
    buyer_rfq_number: Optional[str] = None
    company_name: str = "Lechesa Manaba Consulting and Projects (Pty) Ltd"
    output_dir: Optional[str] = None
    compliance_files: Optional[List[str]] = None


@router.get("/status")
def status():
    return get_quote_pack_v44_status()


@router.post("/generate-from-pdf")
def generate_from_pdf(payload: GenerateFromPdfRequest):
    return generate_quote_pack_from_pdf(
        input_pdf=payload.input_pdf,
        buyer_rfq_number=payload.buyer_rfq_number,
        company_name=payload.company_name,
        output_dir=payload.output_dir,
        margin_percent=payload.margin_percent,
        minimum_profit_required=payload.minimum_profit_required,
        apply_profit_floor=payload.apply_profit_floor,
        min_confidence=payload.min_confidence,
        compliance_files=payload.compliance_files,
    )


@router.post("/generate-from-v43-json")
def generate_from_v43_json(payload: GenerateFromV43JsonRequest):
    return generate_quote_pack_from_v43_json(
        v43_json_path=payload.v43_json_path,
        buyer_rfq_number=payload.buyer_rfq_number,
        company_name=payload.company_name,
        output_dir=payload.output_dir,
        compliance_files=payload.compliance_files,
    )
