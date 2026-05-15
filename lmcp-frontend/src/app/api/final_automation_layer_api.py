from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body

from app.services.final_automation_layer_service import (
    final_go_live_check,
    get_final_automation_status,
    run_final_automation_once,
)

router = APIRouter(prefix="/final-automation", tags=["Final Automation"])


@router.get("/status")
def status() -> Dict[str, Any]:
    return get_final_automation_status()


@router.get("/go-live-check")
def go_live_check() -> Dict[str, Any]:
    return final_go_live_check()


@router.post("/run-once")
def run_once(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    return run_final_automation_once(payload)
