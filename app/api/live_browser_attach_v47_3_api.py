from __future__ import annotations

import inspect
import json
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

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
    attachments: list[str] = Field(default_factory=list)


@router.get("/status")
async def status() -> Dict[str, Any]:
    result = get_v47_3_status()

    if inspect.isawaitable(result):
        result = await result

    return result


@router.post("/attach-and-assist")
async def attach_and_assist(payload: AttachAndAssistRequest) -> Dict[str, Any]:
    try:
        plan_raw = payload.autofill_plan_json

        try:
            plan = json.loads(plan_raw) if plan_raw else {}
        except Exception:
            plan = {"raw_autofill_plan_json": plan_raw}

        plan["attachments"] = payload.attachments
        plan["attachment_paths"] = payload.attachments
        plan["allow_final_submit"] = False

        autofill_plan_json = json.dumps(plan)

        service_payload = {
            "attachments": payload.attachments,
            "submission_attachments": payload.attachments,
            "supporting_documents": payload.attachments,
            "documents": payload.attachments,
            "resolved_attachments": payload.attachments,
        }

        result = attach_to_live_browser_and_assist(
            autofill_plan_json=autofill_plan_json,
            cdp_url=payload.cdp_url,
            output_dir=payload.output_dir,
            fill_visible_fields=payload.fill_visible_fields,
            capture_screenshots=payload.capture_screenshots,
            stop_before_submit=payload.stop_before_submit,
            payload=service_payload,
        )
        
        if inspect.isawaitable(result):
            result = await result

        if isinstance(result, dict):
            return result

        return {
            "status": "ok",
            "service_version": "V47_3_LIVE_BROWSER_ATTACH",
            "result": result,
        }

    except Exception as exc:
        return {
            "status": "error",
            "service_version": "V47_3_LIVE_BROWSER_ATTACH",
            "message": "Live browser attach failed.",
            "error": str(exc),
            "cdp_url": payload.cdp_url,
            "safety": {
                "captcha_bypass_allowed": False,
                "final_submit_blocked": True,
                "operator_must_review": True,
            },
        }
