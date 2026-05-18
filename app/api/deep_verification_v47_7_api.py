
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.services.deep_verification_v47_7_service import get_v47_7_status, run_deep_verification_audit

router = APIRouter(prefix="/v47-deep-verification", tags=["V47.7 Deep Verification Audit"])


class DeepVerificationRequest(BaseModel):
    buyer_rfq_number: str
    quote_number: Optional[str] = None
    description_hint: Optional[str] = None
    final_submission_run_json: Optional[str] = None
    verification_v47_6_json: Optional[str] = None
    cdp_url: str = "http://127.0.0.1:9222"
    output_dir: Optional[str] = None
    register_path: str = "runtime/submission_history/v47_7_verified_submission_register.json"
    navigate_to_profile_responses: bool = True
    profile_responses_url: str = "https://www.etenders.gov.za/Profile#ResponsesSubmitted"
    capture_screenshots: bool = True
    expand_matching_row: bool = True
    wait_ms: int = Field(5000, ge=1000, le=20000)


@router.get("/status")
def status():
    return get_v47_7_status()


@router.post("/run-audit")
def run_audit(payload: DeepVerificationRequest):
    return run_deep_verification_audit(**payload.model_dump())
