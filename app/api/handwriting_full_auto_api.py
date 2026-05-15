"""
LMCP AutoQuote - V16 Full Auto Handwriting API

Drop-in target:
    app/api/handwriting_full_auto_api.py
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.services.handwriting_full_auto_service import (
    example_payload,
    get_full_auto_status,
    run_full_auto_handwriting_completion,
)

router = APIRouter(
    prefix="/handwriting-full-auto",
    tags=["Handwriting Full Auto"],
)


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_full_auto_status()


@router.get("/example-payload")
def get_example_payload() -> Dict[str, Any]:
    return {
        "status": "ok",
        "payload": example_payload(),
    }


@router.post("/complete")
def complete(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = run_full_auto_handwriting_completion(payload)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result)
    return result

