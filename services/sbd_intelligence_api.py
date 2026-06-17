"""
LMCP AutoQuote — SBD Intelligence API V19
File: app/api/sbd_intelligence_api.py

This file keeps the existing /sbd-intelligence/complete endpoint,
but routes it through the V19 precision engine.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.services.sbd_precision_engine_v19 import (
    ENGINE_VERSION,
    complete_sbd_form_v19,
    get_v19_status,
)

router = APIRouter(prefix="/sbd-intelligence", tags=["SBD Intelligence"])


@router.get("/status")
def sbd_intelligence_status() -> Dict[str, Any]:
    return get_v19_status()


@router.get("/example-payload")
def sbd_intelligence_example_payload() -> Dict[str, Any]:
    return {
        "status": "ok",
        "engine_version": ENGINE_VERSION,
        "payload": {
            "buyer_rfq_number": "TEST-V19-CORPORATE-GIFTS",
            "input_pdf": str(Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "playwright" / "downloads" / "RFQ  Corporate Gift Packs.pdf"),
            "reference_image": str(Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "handwriting_simulation" / "clean_ink_cropped.png"),
            "signature_image": str(Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "handwriting_simulation" / "signature.png"),
            "ink_color": "black",
            "debug": True,
            "handwritten_mode": True,
            "buyer_name": "iSIMANGALISO WETLAND PARK AUTHORITY",
            "bid_description": "RFQ: APPOINTMENT OF SERVICE PROVIDER FOR PROCUREMENT OF CORPORATE GIFT PACKS",
            "company_name": "Lechesa Manaba Consulting and Projects (Pty) Ltd",
            "director_name": "Lechesa Manaba",
            "designation": "Director",
            "fields": [
                {"page": 1, "x": 72, "y": 105, "text": "Lechesa Manaba Consulting and Projects (Pty) Ltd", "field_name": "company_name"},
                {"page": 1, "x": 72, "y": 122, "text": "Lechesa Manaba", "field_name": "director_name"},
                {"page": 1, "x": 72, "y": 139, "text": "Director", "field_name": "designation"}
            ],
            "signature_position": {"page": 1, "x": 72, "y": 220, "width": 120, "height": 42}
        },
    }


@router.post("/complete")
def complete_sbd_intelligence(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = complete_sbd_form_v19(payload)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result)
    return result
