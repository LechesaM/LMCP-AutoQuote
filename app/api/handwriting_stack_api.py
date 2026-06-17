from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from app.services.handwriting_glyph_service import get_glyph_status
from app.services.handwriting_line_ink_v5 import get_line_ink_status
from app.services.handwriting_simulation_service import get_handwriting_status

router = APIRouter(prefix="/handwriting-stack", tags=["Handwriting Stack"])


@router.get("/status")
def handwriting_stack_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "handwriting_stack",
        "message": "Combined status for glyph, line-ink, simulation, and form overlay handwriting services.",
        "components": {
            "glyph": get_glyph_status(),
            "line_ink": get_line_ink_status(),
            "simulation": get_handwriting_status(),
            "form_overlay": {
                "status": "ok",
                "service": "handwriting_form_overlay_service",
                "message": "Ready to write handwriting-style text onto existing buyer PDF/SBD/MBD forms.",
            },
        },
    }


@router.get("/example-payload")
def handwriting_stack_example_payload() -> Dict[str, Any]:
    return {
        "status": "ok",
        "payload": {
            "glyph": "GET /handwriting-glyph/status",
            "line_ink": "GET /handwriting-line-ink-v5/status",
            "simulation": "GET /handwriting-simulation/status",
            "form_overlay": "POST /handwriting-form/overlay-existing-pdf",
        },
    }
