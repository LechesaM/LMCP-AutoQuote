
from __future__ import annotations
from typing import Any, Dict
from fastapi import APIRouter
from app.services.tender_form_intelligence_engine import (
    build_glyph_library, complete_tender_form_intelligence, detect_sbd_pages,
    detect_training_template, get_tender_form_intelligence_status, locate_writable_fields,
)
router = APIRouter(prefix="/tender-form-intelligence", tags=["Tender Form Intelligence"])

@router.get("/status")
def status() -> Dict[str, Any]:
    return get_tender_form_intelligence_status()

@router.post("/build-glyphs")
def build_glyphs(payload: Dict[str, Any]) -> Dict[str, Any]:
    return build_glyph_library(payload.get("reference_image") or payload.get("glyph_reference_image") or "", force=bool(payload.get("force", True)))

@router.post("/complete")
def complete(payload: Dict[str, Any]) -> Dict[str, Any]:
    return complete_tender_form_intelligence(payload)

@router.post("/detect-template")
def detect_template(payload: Dict[str, Any]) -> Dict[str, Any]:
    return detect_training_template(payload.get("input_pdf") or payload.get("pdf_path") or "")

@router.post("/detect-sbd")
def detect_sbd(payload: Dict[str, Any]) -> Dict[str, Any]:
    return detect_sbd_pages(payload.get("input_pdf") or payload.get("pdf_path") or "")

@router.post("/locate-fields")
def locate_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    return locate_writable_fields(payload.get("input_pdf") or payload.get("pdf_path") or "", int(payload.get("page") or payload.get("page_number") or 1), int(payload.get("limit") or 30))
