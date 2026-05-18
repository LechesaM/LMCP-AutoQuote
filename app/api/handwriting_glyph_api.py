
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from app.services.handwriting_glyph_service import (
    DEFAULT_SAMPLE_IMAGE,
    GlyphOverlayRequest,
    build_glyph_cache,
    overlay_glyph_handwriting_on_pdf,
)

router = APIRouter(prefix="/handwriting-glyph", tags=["Handwriting Glyph Engine"])


@router.get("/status")
def handwriting_glyph_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "handwriting_glyph_engine",
        "message": "Ready to use saved handwriting image glyphs on existing PDF forms.",
        "sample_image": str(DEFAULT_SAMPLE_IMAGE),
    }


@router.post("/build-cache")
def handwriting_glyph_build_cache() -> Dict[str, Any]:
    return build_glyph_cache(force=True)


@router.get("/example-payload")
def handwriting_glyph_example_payload() -> Dict[str, Any]:
    return {
        "status": "ok",
        "payload": {
            "buyer_rfq_number": "TEST-GLYPH-HANDWRITING-001",
            "input_pdf": "runtime/test_tender_pack/RFQ 4254.pdf",
            "fields": [
                {
                    "page": 1,
                    "x": 120,
                    "y": 720,
                    "text": "Lechesa Manaba Consulting and Projects Pty Ltd",
                    "glyph_height": 14,
                    "letter_spacing": 1,
                    "word_spacing": 8,
                    "max_width": 380,
                },
                {
                    "page": 1,
                    "x": 120,
                    "y": 695,
                    "text": "Lechesa Manaba",
                    "glyph_height": 15,
                    "letter_spacing": 1,
                    "word_spacing": 8,
                },
                {
                    "page": 1,
                    "x": 120,
                    "y": 670,
                    "text": "Director",
                    "glyph_height": 15,
                    "letter_spacing": 1,
                    "word_spacing": 8,
                },
            ],
        },
    }


@router.post("/overlay-existing-pdf")
def handwriting_glyph_overlay_existing_pdf(payload: GlyphOverlayRequest) -> Dict[str, Any]:
    return overlay_glyph_handwriting_on_pdf(payload)
