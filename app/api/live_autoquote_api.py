from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.services.live_autoquote_runner import LiveAutoQuoteRunner

router = APIRouter(prefix="/live-autoquote", tags=["Live AutoQuote"])


class LiveAutoQuoteRunRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recipient_email: str
    company_data: Optional[Dict[str, Any]] = None
    cc_email: Optional[str] = None
    margin_percent: float = Field(25.0, ge=0.0, le=100.0)
    include_docx: bool = True
    include_pdf: bool = True
    max_items: int = Field(10, ge=1, le=100)


@router.get("/health")
def health() -> Dict[str, Any]:
    return {
        "success": True,
        "message": "Live AutoQuote runner is ready",
    }


@router.post("/run")
def run_live_autoquote(request: LiveAutoQuoteRunRequest) -> Dict[str, Any]:
    return LiveAutoQuoteRunner.run(
        recipient_email=request.recipient_email,
        company_data=request.company_data,
        cc_email=request.cc_email,
        margin_percent=request.margin_percent,
        include_docx=request.include_docx,
        include_pdf=request.include_pdf,
        max_items=request.max_items,
    )
