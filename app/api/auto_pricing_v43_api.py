from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.auto_pricing_v43_service import (
    auto_price_from_v42_json,
    auto_price_pdf_with_v42,
    get_auto_pricing_status,
)

router = APIRouter(prefix="/v43-auto-pricing", tags=["V43 Auto Pricing Engine"])


class AutoPricePdfRequest(BaseModel):
    input_pdf: str
    buyer_rfq_number: Optional[str] = None
    max_pages_scan: int = Field(25, ge=1, le=100)
    output_dir: Optional[str] = None
    margin_percent: float = Field(25.0, ge=1.0, le=90.0)
    minimum_profit_required: float = Field(30000.0, ge=0.0)
    vat_rate_percent: float = Field(15.0, ge=0.0, le=30.0)
    apply_profit_floor: bool = True
    min_confidence: float = Field(0.35, ge=0.0, le=1.0)


class AutoPriceV42JsonRequest(BaseModel):
    v42_json_path: str
    buyer_rfq_number: Optional[str] = None
    output_dir: Optional[str] = None
    margin_percent: float = Field(25.0, ge=1.0, le=90.0)
    minimum_profit_required: float = Field(30000.0, ge=0.0)
    vat_rate_percent: float = Field(15.0, ge=0.0, le=30.0)
    apply_profit_floor: bool = True


@router.get("/status")
def status():
    return get_auto_pricing_status()


@router.post("/auto-price-pdf")
def auto_price_pdf(payload: AutoPricePdfRequest):
    return auto_price_pdf_with_v42(
        input_pdf=payload.input_pdf,
        buyer_rfq_number=payload.buyer_rfq_number,
        max_pages_scan=payload.max_pages_scan,
        output_dir=payload.output_dir,
        margin_percent=payload.margin_percent,
        minimum_profit_required=payload.minimum_profit_required,
        vat_rate_percent=payload.vat_rate_percent,
        apply_profit_floor=payload.apply_profit_floor,
        min_confidence=payload.min_confidence,
    )


@router.post("/auto-price-v42-json")
def auto_price_v42_json(payload: AutoPriceV42JsonRequest):
    return auto_price_from_v42_json(
        v42_json_path=payload.v42_json_path,
        buyer_rfq_number=payload.buyer_rfq_number,
        output_dir=payload.output_dir,
        margin_percent=payload.margin_percent,
        minimum_profit_required=payload.minimum_profit_required,
        vat_rate_percent=payload.vat_rate_percent,
        apply_profit_floor=payload.apply_profit_floor,
    )
