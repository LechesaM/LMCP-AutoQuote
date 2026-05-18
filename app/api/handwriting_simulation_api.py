"""
LMCP AutoQuote - Handwriting Simulation API
V13 Identity Engine Router

Drop-in target:
    app/api/handwriting_simulation_api.py
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.services.handwriting_simulation_service import (
    complete_handwriting_form,
    example_payload,
    get_handwriting_status,
    run_handwriting_simulation,
    simulate_handwriting,
)

router = APIRouter(
    prefix="/handwriting-simulation",
    tags=["Handwriting Simulation"],
)


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_handwriting_status()


@router.get("/example-payload")
def get_example_payload() -> Dict[str, Any]:
    return {
        "status": "ok",
        "payload": example_payload(),
    }


@router.post("/complete-form")
def complete_form(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = complete_handwriting_form(payload)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result)
    return result


@router.post("/simulate")
def simulate(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = simulate_handwriting(payload)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result)
    return result


@router.post("/run")
def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = run_handwriting_simulation(payload)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result)
    return result

