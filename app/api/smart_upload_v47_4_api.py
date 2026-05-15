
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from app.services.smart_upload_v47_4_service import attach_and_smart_upload, get_v47_4_status

router = APIRouter(prefix="/v47-smart-upload", tags=["V47.4 Smart Upload Engine"])


class AttachAndUploadRequest(BaseModel):
    autofill_plan_json: str
    cdp_url: str = "http://127.0.0.1:9222"
    output_dir: Optional[str] = None
    execute_uploads: bool = False
    capture_screenshots: bool = True
    stop_before_submit: bool = True


@router.get("/status")
def status():
    return get_v47_4_status()


@router.post("/attach-and-upload")
def attach_and_upload(payload: AttachAndUploadRequest):
    return attach_and_smart_upload(
        autofill_plan_json=payload.autofill_plan_json,
        cdp_url=payload.cdp_url,
        output_dir=payload.output_dir,
        execute_uploads=payload.execute_uploads,
        capture_screenshots=payload.capture_screenshots,
        stop_before_submit=payload.stop_before_submit,
    )
