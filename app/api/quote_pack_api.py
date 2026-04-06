from __future__ import annotations

from fastapi import APIRouter

from app.quote_pack_models import (
    AutoQuotePipelineRequest,
    AutoQuotePipelineResponse,
    QuotePackBuildRequest,
    QuotePackBuildResponse,
)
from app.services.autoquote_pipeline import AutoQuotePipelineService
from app.services.quote_pack_service import QuotePackService

router = APIRouter(prefix="/quote-pack", tags=["Quote Pack"])


@router.get("/health")
def quote_pack_health():
    return {
        "success": True,
        "message": "Quote pack service is running",
        "features": [
            "real-data-payload",
            "docx-generation",
            "pdf-generation",
            "autoquote-pipeline",
        ],
    }


@router.post("/build", response_model=QuotePackBuildResponse)
def build_quote_pack(request: QuotePackBuildRequest):
    return QuotePackService.build_quote_pack(
        rfq_data=request.rfq_data,
        quote_data=request.quote_data,
        company_data=request.company_data,
        margin_percent=request.margin_percent,
        include_docx=False,
        include_pdf=True,
    )


@router.post("/run-autoquote", response_model=AutoQuotePipelineResponse)
def run_autoquote_pipeline(request: AutoQuotePipelineRequest):
    return AutoQuotePipelineService.run_pipeline(
        rfq_data=request.rfq_data,
        company_data=request.company_data,
        recipient_email=request.recipient_email,
        cc_email=request.cc_email,
        margin_percent=request.margin_percent,
        include_docx=False,
        include_pdf=True,
        email_subject=request.email_subject,
        email_body=request.email_body,
    )
