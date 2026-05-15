
from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter

from app.services.tender_form_intelligence_engine import (
    complete_tender_form_intelligence,
    detect_sbd_pages,
    detect_training_template,
    get_tender_form_intelligence_status,
    locate_writable_fields,
)

router = APIRouter(prefix="/sbd-intelligence", tags=["SBD Intelligence"])


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_tender_form_intelligence_status()


@router.post("/complete")
def complete(payload: Dict[str, Any]) -> Dict[str, Any]:
    return complete_tender_form_intelligence(payload)


@router.post("/detect-sbd")
def detect_sbd(payload: Dict[str, Any]) -> Dict[str, Any]:
    return detect_sbd_pages(payload.get("input_pdf") or payload.get("pdf_path") or "")


@router.post("/detect-template")
def detect_template(payload: Dict[str, Any]) -> Dict[str, Any]:
    return detect_training_template(payload.get("input_pdf") or payload.get("pdf_path") or "")


@router.post("/locate-fields")
def locate_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    return locate_writable_fields(
        input_pdf=payload.get("input_pdf") or payload.get("pdf_path") or "",
        page_number=int(payload.get("page") or payload.get("page_number") or 1),
        limit=int(payload.get("limit") or 30),
    )


@router.get("/example-payload")
def example_payload() -> Dict[str, Any]:
    return {
        "status": "ok",
        "payload_training_map": {
            "buyer_rfq_number": "TEST-V21-3-TRAINING-MAP",
            "input_pdf": "runtime/playwright/downloads/RFQ_Corporate_Gift_Packs.pdf",
            "signature_image": "runtime/handwriting_simulation/signature.png",
            "ink_color": "black",
            "training_map": True,
            "auto_fill": True,
            "buyer_name": "iSIMANGALISO WETLAND PARK AUTHORITY",
            "bid_description": "SUPPLY AND DELIVERY OF CORPORATE GIFT PACKS"
        }
    }
