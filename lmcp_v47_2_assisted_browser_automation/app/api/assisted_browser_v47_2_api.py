
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.assisted_browser_v47_2_service import (
    get_v47_2_status,
    run_assisted_browser_from_plan,
)

router = APIRouter(prefix="/v47-assisted-browser", tags=["V47.2 Assisted Browser Automation"])


class RunFromPlanRequest(BaseModel):
    autofill_plan_json: str
    output_dir: Optional[str] = None
    headless: bool = True
    timeout_ms: int = Field(60000, ge=10000, le=180000)
    stop_before_submit: bool = True


@router.get("/status")
def status():
    return get_v47_2_status()


@router.post("/run-from-plan")
def run_from_plan(payload: RunFromPlanRequest):
    return run_assisted_browser_from_plan(
        autofill_plan_json=payload.autofill_plan_json,
        output_dir=payload.output_dir,
        headless=payload.headless,
        timeout_ms=payload.timeout_ms,
        stop_before_submit=payload.stop_before_submit,
    )
