
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter

from app.services.handwriting_glyph_service import (
    DEFAULT_SAMPLE_IMAGE,
    GlyphOverlayRequest,
    build_glyph_cache,
    example_payload,
    get_glyph_status,
    overlay_glyph_handwriting_on_pdf,
)

router = APIRouter(prefix="/handwriting-glyph", tags=["Handwriting Glyph Engine"])


@router.get("/status")
def handwriting_glyph_status() -> Dict[str, Any]:
    return get_glyph_status()


@router.post("/build-cache")
def handwriting_glyph_build_cache(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}
    return build_glyph_cache(
        sample_image=payload.get("sample_image"),
        force=bool(payload.get("force", True)),
    )


@router.get("/example-payload")
def handwriting_glyph_example_payload() -> Dict[str, Any]:
    return {
        "status": "ok",
        "payload": example_payload(),
    }


@router.post("/overlay-existing-pdf")
def handwriting_glyph_overlay_existing_pdf(payload: GlyphOverlayRequest) -> Dict[str, Any]:
    return overlay_glyph_handwriting_on_pdf(payload)
