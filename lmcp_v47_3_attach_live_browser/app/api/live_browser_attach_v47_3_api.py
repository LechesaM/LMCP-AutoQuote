
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from app.services.live_browser_attach_v47_3_service import (
    attach_to_live_browser_and_assist,
    get_v47_3_status,
)

router = APIRouter(prefix="/v47-live-browser", tags=["V47.3 Live Browser Attach"])


class AttachAndAssistRequest(BaseModel):
    autofill_plan_json: str
    cdp_url: str = "http://127.0.0.1:9222"
    output_dir: Optional[str] = None
    fill_visible_fields: bool = True
    capture_screenshots: bool = True
    stop_before_submit: bool = True


@router.get("/status")
def status():
    return get_v47_3_status()


@router.post("/attach-and-assist")
def attach_and_assist(payload: AttachAndAssistRequest):
    return attach_to_live_browser_and_assist(
        autofill_plan_json=payload.autofill_plan_json,
        cdp_url=payload.cdp_url,
        output_dir=payload.output_dir,
        fill_visible_fields=payload.fill_visible_fields,
        capture_screenshots=payload.capture_screenshots,
        stop_before_submit=payload.stop_before_submit,
    )
