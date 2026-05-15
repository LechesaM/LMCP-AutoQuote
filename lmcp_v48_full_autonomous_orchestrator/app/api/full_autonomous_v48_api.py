
from __future__ import annotations

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
    cdp_url: str = "http://127.0.0.1:9222"
    output_dir: Optional[str] = None
    override_policy: Optional[Dict[str, Any]] = None


class RunFromV45WorkspaceRequest(BaseModel):
    v45_workspace: str
    buyer_rfq_number: str
    buyer_name: Optional[str] = None
    portal_url: Optional[str] = "https://www.etenders.gov.za"
    submission_method: str = "portal"
    cdp_url: str = "http://127.0.0.1:9222"
    output_dir: Optional[str] = None
    override_policy: Optional[Dict[str, Any]] = None


@router.get("/status")
def status():
    return get_v48_status()


@router.post("/policy")
def update_policy(payload: PolicyRequest):
    return set_v48_autonomous_policy(**payload.model_dump())


@router.post("/run-from-pdf")
def api_run_from_pdf(payload: RunFromPdfRequest):
    return run_v48_from_pdf(**payload.model_dump())


@router.post("/run-from-v45-workspace")
def api_run_from_v45_workspace(payload: RunFromV45WorkspaceRequest):
    return run_v48_from_v45_workspace(**payload.model_dump())
