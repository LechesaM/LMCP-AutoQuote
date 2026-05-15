from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from app.services.handwriting_simulation_service import (
    build_example_overlay_payload,
    create_handwriting_overlay_pdf,
    get_handwriting_status,
    preview_handwriting_payload,
)

router = APIRouter(prefix="/handwriting-simulation", tags=["handwriting-simulation"])


@router.get("/status")
def status(limit: int = 50) -> Dict[str, Any]:
    return get_handwriting_status(limit=limit)


@router.get("/example-payload")
def example_payload() -> Dict[str, Any]:
    return {
        "status": "ok",
        "payload": build_example_overlay_payload(),
    }


@router.post("/preview")
def preview(payload: Dict[str, Any]) -> Dict[str, Any]:
    return preview_handwriting_payload(payload)


@router.post("/overlay")
def overlay(payload: Dict[str, Any]) -> Dict[str, Any]:
    return create_handwriting_overlay_pdf(payload)
