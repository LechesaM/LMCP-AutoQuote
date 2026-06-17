
from __future__ import annotations

import os
from typing import Any, Dict, Optional
from fastapi import APIRouter
from pydantic import BaseModel

from app.services.full_autonomous_v48_service import (
    get_v48_status,
    set_v48_autonomous_policy,
    run_v48_from_pdf,
    run_v48_from_v45_workspace,
)

router = APIRouter(prefix="/v48-autonomous", tags=["V48 Full Autonomous Orchestrator"])
V48_AUTONOMOUS_API_ENABLED = (
    str(os.getenv("V48_AUTONOMOUS_API_ENABLED", "false")).strip().lower() in {"1", "true", "yes", "on"}
)


def _disabled_response(action: str) -> Dict[str, Any]:
    return {
        "status": "disabled",
        "action": action,
        "message": "V48 autonomous API actions are disabled by default.",
        "api_enabled": V48_AUTONOMOUS_API_ENABLED,
    }


class PolicyRequest(BaseModel):
    enabled: Optional[bool] = None
    mode: Optional[str] = None
    allow_email_send: Optional[bool] = None
    allow_portal_upload: Optional[bool] = None
    allow_portal_final_submit: Optional[bool] = None
    minimum_profit_required: Optional[float] = None
    margin_percent: Optional[float] = None


class RunFromPdfRequest(BaseModel):
    input_pdf: str
    buyer_rfq_number: str
    buyer_name: Optional[str] = None
    portal_url: Optional[str] = "https://www.etenders.gov.za"
    submission_method: str = "portal"
    cdp_url: Optional[str] = None
    output_dir: Optional[str] = None
    override_policy: Optional[Dict[str, Any]] = None


class RunFromV45WorkspaceRequest(BaseModel):
    v45_workspace: str
    buyer_rfq_number: str
    buyer_name: Optional[str] = None
    portal_url: Optional[str] = "https://www.etenders.gov.za"
    submission_method: str = "portal"
    cdp_url: Optional[str] = None
    output_dir: Optional[str] = None
    override_policy: Optional[Dict[str, Any]] = None


@router.get("/status")
def status():
    payload = get_v48_status()
    payload["api_enabled"] = V48_AUTONOMOUS_API_ENABLED
    return payload


@router.post("/policy")
def update_policy(payload: PolicyRequest):
    if not V48_AUTONOMOUS_API_ENABLED:
        return _disabled_response("policy")
    return set_v48_autonomous_policy(**payload.model_dump())


@router.post("/run-from-pdf")
def api_run_from_pdf(payload: RunFromPdfRequest):
    if not V48_AUTONOMOUS_API_ENABLED:
        return _disabled_response("run-from-pdf")
    return run_v48_from_pdf(**payload.model_dump())


@router.post("/run-from-v45-workspace")
def api_run_from_v45_workspace(payload: RunFromV45WorkspaceRequest):
    if not V48_AUTONOMOUS_API_ENABLED:
        return _disabled_response("run-from-v45-workspace")
    return run_v48_from_v45_workspace(**payload.model_dump())

@router.get("/last-result")
def last_result():
    from pathlib import Path
    import json

    root = Path("runtime/full_autonomous_v48")
    files = sorted(root.glob("*/v48_autonomous_run.json"), key=lambda x: x.stat().st_mtime, reverse=True)
    if not files:
        return {"status": "empty", "message": "No V48 runs found."}

    return json.loads(files[0].read_text())


@router.get("/history")
def history(limit: int = 20):
    from pathlib import Path
    import json

    root = Path("runtime/full_autonomous_v48")
    files = sorted(root.glob("*/v48_autonomous_run.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]

    items = []
    for f in files:
        try:
            data = json.loads(f.read_text())
            items.append({
                "status": data.get("status"),
                "buyer_rfq_number": data.get("buyer_rfq_number"),
                "quote_number": data.get("quote_number"),
                "submission_method": data.get("submission_method"),
                "started_at": data.get("started_at"),
                "completed_at": data.get("completed_at"),
                "workspace": data.get("workspace"),
                "message": data.get("message"),
            })
        except Exception:
            pass

    return {"status": "ok", "count": len(items), "items": items}


@router.get("/policy")
def get_policy():
    return status().get("policy", {})

