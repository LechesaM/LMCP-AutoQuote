"""
LMCP AutoQuote - Handwriting Field Detector API
V15 Auto-Detect Fields Router

Drop-in target:
    app/api/handwriting_field_detector_api.py
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.services.handwriting_field_detector_service import (
    build_handwriting_payload_from_detection,
    detect_pdf_fields,
    example_payload,
    get_field_detector_status,
)

router = APIRouter(
    prefix="/handwriting-field-detector",
    tags=["Handwriting Field Detector"],
)


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_field_detector_status()


@router.get("/example-payload")
def get_example_payload() -> Dict[str, Any]:
    return {
        "status": "ok",
        "payload": example_payload(),
    }


@router.post("/detect")
def detect(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = detect_pdf_fields(payload)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result)
    return result


@router.post("/build-handwriting-payload")
def build_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = build_handwriting_payload_from_detection(payload)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result)
    return result

