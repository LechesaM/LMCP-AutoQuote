"""
LMCP AutoQuote - Handwriting Real Form Overlay API

Drop-in path:
    app/api/handwriting_form_overlay_api.py
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from app.services.handwriting_form_overlay_service import (
    HandwritingFormOverlayRequest,
    overlay_handwriting_on_existing_pdf,
)

router = APIRouter(prefix="/handwriting-form", tags=["Handwriting Real Form Overlay"])


@router.get("/status")
def handwriting_form_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "handwriting_form_overlay",
        "message": "Ready to write handwriting-style text onto existing buyer PDF/SBD/MBD forms.",
        "required_payload_keys": ["buyer_rfq_number", "input_pdf", "fields"],
    }


@router.get("/example-payload")
def handwriting_form_example_payload() -> Dict[str, Any]:
    return {
        "status": "ok",
        "payload": {
            "buyer_rfq_number": "TEST-HANDWRITING-REAL-FORM-001",
            "input_pdf": "runtime/test_tender_pack/sample_buyer_form.pdf",
            "fields": [
                {
                    "page": 1,
                    "x": 120,
                    "y": 720,
                    "text": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
                    "font_size": 10,
                },
                {
                    "page": 1,
                    "x": 120,
                    "y": 695,
                    "text": "Lechesa Manaba",
                    "font_size": 11,
                },
                {
                    "page": 1,
                    "x": 120,
                    "y": 670,
                    "text": "Director",
                    "font_size": 11,
                },
            ],
        },
    }


@router.post("/overlay-existing-pdf")
def handwriting_form_overlay_existing_pdf(payload: HandwritingFormOverlayRequest) -> Dict[str, Any]:
    return overlay_handwriting_on_existing_pdf(payload)
