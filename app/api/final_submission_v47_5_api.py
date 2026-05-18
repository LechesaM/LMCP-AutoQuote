
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.final_submission_v47_5_service import get_v47_5_status, guarded_final_submission

router = APIRouter(prefix="/v47-final-submit", tags=["V47.5 Guarded Final Submission"])


class GuardedSubmitRequest(BaseModel):
    autofill_plan_json: str
    cdp_url: str = "http://host.docker.internal:9222"
    output_dir: Optional[str] = None
    pack_id: Optional[str] = None
    dry_run: bool = True
    execute_final_submit: bool = False
    confirmation_phrase: Optional[str] = None
    capture_screenshots: bool = True
    wait_after_click_ms: int = Field(3000, ge=500, le=15000)


@router.get("/status")
def status():
    return get_v47_5_status()


@router.post("/guarded-submit")
async def guarded_submit(payload: GuardedSubmitRequest):
    result = await guarded_final_submission(
        autofill_plan_json=payload.autofill_plan_json,
        cdp_url=payload.cdp_url,
        output_dir=payload.output_dir,
        dry_run=payload.dry_run,
        execute_final_submit=payload.execute_final_submit,
        confirmation_phrase=payload.confirmation_phrase,
        capture_screenshots=payload.capture_screenshots,
        wait_after_click_ms=payload.wait_after_click_ms,
        pack_id=payload.pack_id,
    )
    if isinstance(result, dict) and not result.get("submitted"):
        blocked_reason = result.get("blocked_reason") or result.get("final_block_reason") or result.get("reason") or "Final submission is blocked."
        raise HTTPException(status_code=409, detail={**result, "blocked_reason": blocked_reason})
    return result
