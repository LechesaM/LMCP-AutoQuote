from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body

from app.services import tender_form_intelligence_engine as engine

router = APIRouter(prefix="/sbd-intelligence", tags=["SBD Intelligence"])


@router.get("/status")
def sbd_intelligence_status() -> Dict[str, Any]:
    """
    Status endpoint for the V22.3 Stroke Flow Engine.
    """
    if hasattr(engine, "get_tender_form_intelligence_status"):
        return engine.get_tender_form_intelligence_status()
    if hasattr(engine, "get_status"):
        return engine.get_status()
    if hasattr(engine, "status"):
        return engine.status()

    return {
        "status": "ok",
        "engine_version": getattr(engine, "ENGINE_VERSION", "unknown"),
        "message": "SBD intelligence API is loaded, but no engine status function was found.",
    }


@router.get("/example-payload")
def sbd_intelligence_example_payload() -> Dict[str, Any]:
    """
    Example payload for completing an SBD/tender form.
    """
    if hasattr(engine, "example_payload"):
        return {
            "status": "ok",
            "engine_version": getattr(engine, "ENGINE_VERSION", "unknown"),
            "payload": engine.example_payload(),
        }

    return {
        "status": "ok",
        "engine_version": getattr(engine, "ENGINE_VERSION", "unknown"),
        "payload": {
            "buyer_rfq_number": "TEST-V22.3-STROKE-FLOW",
            "input_pdf": "runtime/playwright/downloads/example.pdf",
            "reference_image": "runtime/handwriting_simulation/clean_ink_cropped.png",
            "signature_image": "runtime/handwriting_simulation/signature.png",
            "ink_color": "black",
            "debug": True,
            "buyer_name": "BUYER NAME",
            "bid_description": "RFQ DESCRIPTION",
        },
    }


@router.post("/complete")
def sbd_intelligence_complete(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """
    Complete an SBD/tender PDF using the V22.3 Stroke Flow Engine.
    """
    if hasattr(engine, "complete_tender_form"):
        return engine.complete_tender_form(payload)

    if hasattr(engine, "complete_tender_form_intelligence"):
        return engine.complete_tender_form_intelligence(payload)

    if hasattr(engine, "complete_sbd_form"):
        return engine.complete_sbd_form(payload)

    if hasattr(engine, "run_tender_form_intelligence"):
        return engine.run_tender_form_intelligence(payload)

    if hasattr(engine, "run"):
        return engine.run(payload)

    return {
        "status": "error",
        "engine_version": getattr(engine, "ENGINE_VERSION", "unknown"),
        "message": "No compatible completion function found in tender_form_intelligence_engine.py",
    }


@router.post("/classify")
def sbd_intelligence_classify(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    """
    Optional compatibility endpoint.
    """
    if hasattr(engine, "classify_tender_form"):
        return engine.classify_tender_form(payload)

    return {
        "status": "ok",
        "engine_version": getattr(engine, "ENGINE_VERSION", "unknown"),
        "classification": "sbd_or_tender_form",
        "message": "Classifier compatibility endpoint loaded.",
    }


@router.post("/detect-fields")
def sbd_intelligence_detect_fields(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """
    Optional compatibility endpoint for field detection.
    """
    if hasattr(engine, "detect_tender_form_fields"):
        return engine.detect_tender_form_fields(payload)

    if hasattr(engine, "detect_fields"):
        return engine.detect_fields(payload)

    input_pdf: Optional[str] = payload.get("input_pdf") or payload.get("pdf_path")
    if input_pdf and hasattr(engine, "build_field_plan"):
        return engine.build_field_plan(input_pdf, payload)

    return {
        "status": "error",
        "engine_version": getattr(engine, "ENGINE_VERSION", "unknown"),
        "message": "No compatible field detection function found.",
    }


@router.post("/build-glyph-library")
def sbd_intelligence_build_glyph_library(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    """
    Legacy endpoint retained for old frontend/API calls.
    V22.3 uses dynamic stroke-flow rendering instead of a static glyph cache.
    """
    if hasattr(engine, "build_glyph_library"):
        return engine.build_glyph_library(payload)

    return {
        "status": "ok",
        "engine_version": getattr(engine, "ENGINE_VERSION", "unknown"),
        "message": "V22.3 uses dynamic stroke-flow rendering; no glyph cache is required.",
        "dynamic_stroke_flow": True,
    }

