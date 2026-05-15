
"""
LMCP AutoQuote System
V21 Tender Form Intelligence API

Drop-in target:
    app/api/tender_form_intelligence_api.py

Router prefix:
    /sbd-intelligence
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from app.services.tender_form_intelligence_engine import (
    complete_tender_form_intelligence,
    get_tender_form_intelligence_status,
)

router = APIRouter(prefix="/sbd-intelligence", tags=["SBD Intelligence"])


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_tender_form_intelligence_status()


@router.post("/complete")
def complete(payload: Dict[str, Any]) -> Dict[str, Any]:
    return complete_tender_form_intelligence(payload)


@router.get("/example-payload")
def example_payload() -> Dict[str, Any]:
    return {
        "status": "ok",
        "payload": {
            "buyer_rfq_number": "TEST-V21-HANDWRITING",
            "input_pdf": "runtime/playwright/downloads/RFQ Corporate Gift Packs.pdf",
            "reference_image": "runtime/handwriting_simulation/clean_ink_cropped.png",
            "signature_image": "runtime/handwriting_simulation/signature.png",
            "ink_color": "black",
            "debug": True,
            "buyer_name": "iSIMANGALISO WETLAND PARK AUTHORITY",
            "bid_description": "RFQ: APPOINTMENT OF SERVICE PROVIDER FOR PROCUREMENT OF CORPORATE GIFT PACKS",
            "fields": [
                {
                    "page": 1,
                    "x": 120,
                    "y": 720,
                    "w": 360,
                    "h": 30,
                    "text": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
                    "name": "company_name",
                    "font_size": 15
                },
                {
                    "page": 1,
                    "x": 120,
                    "y": 690,
                    "w": 220,
                    "h": 30,
                    "text": "Lechesa Manaba",
                    "name": "director_name",
                    "font_size": 15
                },
                {
                    "page": 1,
                    "x": 120,
                    "y": 660,
                    "w": 180,
                    "h": 30,
                    "text": "Director",
                    "name": "designation",
                    "font_size": 15
                }
            ]
        }
    }
