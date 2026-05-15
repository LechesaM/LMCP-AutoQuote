
from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter

from app.services.tender_form_intelligence_engine import (
    complete_tender_form_intelligence,
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
        "payload_manual": {
            "buyer_rfq_number": "TEST-V21-1-MANUAL",
            "input_pdf": "runtime/playwright/downloads/RFQ_Corporate_Gift_Packs.pdf",
            "reference_image": "runtime/handwriting_simulation/clean_ink_cropped.png",
            "ink_color": "black",
            "debug": True,
            "fields": [
                {
                    "page": 1,
                    "x": 80,
                    "y": 760,
                    "w": 420,
                    "h": 30,
                    "text": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
                    "name": "company_name",
                    "font_size": 14
                }
            ]
        },
        "payload_auto_locator": {
            "buyer_rfq_number": "TEST-V21-1-AUTO",
            "input_pdf": "runtime/playwright/downloads/RFQ_Corporate_Gift_Packs.pdf",
            "reference_image": "runtime/handwriting_simulation/clean_ink_cropped.png",
            "ink_color": "black",
            "debug": True,
            "auto_locate_fields": True,
            "fields": [
                {
                    "page": 1,
                    "name": "company_name",
                    "anchor": "COMPANY",
                    "w": 420,
                    "h": 30,
                    "text": "Lechesa Manaba Consulting and Projects (Pty) Ltd"
                }
            ]
        }
    }
