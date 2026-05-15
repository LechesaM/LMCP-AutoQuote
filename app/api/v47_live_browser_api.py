from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
import inspect

router = APIRouter(prefix="/v47-live-browser", tags=["V47 Live Browser"])


class LiveBrowserAttachPayload(BaseModel):
    cdp_url: str = Field(default="http://host.docker.internal:9222")
    autofill_plan_json: Optional[str] = None
    output_dir: Optional[str] = None
    fill_visible_fields: bool = True
    capture_screenshots: bool = True
    stop_before_submit: bool = True
    allow_final_submit: bool = False


@router.get("/status")
async def get_v47_live_browser_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": "V47_3_LIVE_BROWSER_ATTACH",
        "router": "v47_live_browser_api",
        "safety": {
            "captcha_bypass_allowed": False,
            "final_submit_default": False,
            "operator_controlled": True,
        },
    }


@router.post("/attach-and-assist")
async def attach_and_assist(payload: LiveBrowserAttachPayload) -> Dict[str, Any]:
    data = payload.model_dump()

    try:
        from app.services.v47_live_browser_attach_service import (
            attach_documents_to_live_browser,
        )
    except Exception as exc:
        return {
            "status": "error",
            "service_version": "V47_3_LIVE_BROWSER_ATTACH",
            "message": "Could not import live browser attach service.",
            "error": str(exc),
        }

    try:
        result = attach_documents_to_live_browser(data)

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
            "payload_keys": list(data.keys()),
        }


# Backward-compatible alias
@router.post("/attach-documents")
async def attach_documents(payload: LiveBrowserAttachPayload) -> Dict[str, Any]:
    return await attach_and_assist(payload)
